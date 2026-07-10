"""
OCPP 1.6 ChargePoint 消息处理器
每个充电桩连接对应一个此类的实例
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone

from ocpp.routing import on
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call, call_result
from ocpp.v16.enums import (
    Action,
    AuthorizationStatus,
    RegistrationStatus,
)

from models.database import async_session
from services import cp_service, auth_service, transaction_service
from .message_bus import publish, OcppMessage
from . import handler_config

logger = logging.getLogger("ocpp_server")


class ChargePointHandler(BaseChargePoint):
    """处理单个充电桩的 OCPP 消息"""

    def __init__(self, charge_box_id: str, connection):
        super().__init__(charge_box_id, connection)
        self._charge_point_db_id: int | None = None
        self._pending_actions: dict[str, str] = {}

    async def route_message(self, raw_msg):
        """覆写 route_message，捕获所有入站消息（包括 CALLRESULT）"""
        msg = json.loads(raw_msg) if isinstance(raw_msg, str) else raw_msg
        msg_type, msg_id = msg[0], msg[1]
        if msg_type in (3, 4):
            action = self._pending_actions.pop(msg_id, None)
            payload = msg[2] if len(msg) > 2 else {}
            type_name = "CALLRESULT" if msg_type == 3 else "CALLERROR"
            display_payload = payload if payload else {"raw": raw_msg if isinstance(raw_msg, str) else json.dumps(raw_msg)}
            publish(OcppMessage(charge_box_id=self.id, direction="IN",
                                action=f"{action} ({type_name})" if action else f"[{type_name}]",
                                payload=display_payload, msg_type=msg_type))
        await super().route_message(raw_msg)

    async def _send(self, message):
        """覆写 _send，捕获所有发出的消息"""
        parsed = json.loads(message)
        msg_type, msg_id = parsed[0], parsed[1]
        action = parsed[2] if len(parsed) > 2 and isinstance(parsed[2], str) else None
        payload = parsed[3] if len(parsed) > 3 else parsed[2] if len(parsed) > 2 and isinstance(parsed[2], dict) else {}
        if msg_type == 2 and action:
            self._pending_actions[msg_id] = action
        if msg_type in (3, 4) and not action:
            action = self._pending_actions.pop(msg_id, None)
        msg_type_name = {2: "CALL", 3: "CALLRESULT", 4: "CALLERROR"}.get(msg_type, str(msg_type))
        publish(OcppMessage(
            charge_box_id=self.id, direction="OUT",
            action=f"{action} ({msg_type_name})" if action else f"[{msg_type_name}]",
            payload=payload if isinstance(payload, dict) else {"raw": str(payload)}, msg_type=msg_type,
        ))
        await super()._send(message)

    # ==================== Core Profile 上行消息 ====================

    @on(Action.boot_notification)
    async def on_boot_notification(self, charge_point_vendor: str, charge_point_model: str, **kwargs):
        logger.info(f"[{self.id}] BootNotification: vendor={charge_point_vendor}, model={charge_point_model}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="BootNotification (CALL)",
                            payload={"charge_point_vendor": charge_point_vendor, "charge_point_model": charge_point_model, **kwargs}))
        cfg = handler_config.get_config("boot")
        status = RegistrationStatus.accepted
        interval = 60
        if cfg:
            status = RegistrationStatus.accepted if cfg.status == "Accepted" else RegistrationStatus.pending if cfg.status == "Pending" else RegistrationStatus.rejected
            interval = cfg.interval
            if cfg.behavior == "Delay" and cfg.delay > 0:
                await asyncio.sleep(cfg.delay)
            if cfg.behavior == "Drop":
                return None
        async with async_session() as db:
            cp = await cp_service.register_or_update(
                db=db, charge_box_id=self.id,
                vendor=charge_point_vendor, model=charge_point_model,
                serial_number=kwargs.get("charge_point_serial_number"),
                firmware_version=kwargs.get("firmware_version"),
                iccid=kwargs.get("iccid"), imsi=kwargs.get("imsi"),
                meter_type=kwargs.get("meter_type"),
            )
            self._charge_point_db_id = cp.id
            await db.commit()
        return call_result.BootNotification(current_time=datetime.now(tz=timezone.utc).isoformat(), interval=interval, status=status)

    @on(Action.heartbeat)
    async def on_heartbeat(self):
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="Heartbeat (CALL)", payload={}))
        async with async_session() as db:
            await cp_service.update_heartbeat(db, self.id)
            await db.commit()
        return call_result.Heartbeat(current_time=datetime.now(tz=timezone.utc).isoformat())

    @on(Action.authorize)
    async def on_authorize(self, id_tag: str, **kwargs):
        logger.info(f"[{self.id}] Authorize: id_tag={id_tag}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="Authorize (CALL)", payload={"id_tag": id_tag, **kwargs}))
        cfg = handler_config.get_config("authorize")
        if cfg:
            if cfg.behavior == "Delay" and cfg.delay > 0:
                await asyncio.sleep(cfg.delay)
            if cfg.behavior == "Drop":
                return None
            if cfg.status != "Accepted":
                logger.info(f"[{self.id}] Authorize overridden: {cfg.status}")
                return call_result.Authorize(id_tag_info={"status": cfg.status})
        async with async_session() as db:
            status = await auth_service.authorize(db, id_tag)
            await db.commit()
        return call_result.Authorize(id_tag_info={"status": status})

    @on(Action.start_transaction)
    async def on_start_transaction(self, connector_id: int, id_tag: str, meter_start: int, timestamp: str, **kwargs):
        logger.info(f"[{self.id}] StartTransaction: connector={connector_id}, id_tag={id_tag}, meter_start={meter_start}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="StartTransaction (CALL)",
                            payload={"connector_id": connector_id, "id_tag": id_tag, "meter_start": meter_start, "timestamp": timestamp, **kwargs}))
        cfg = handler_config.get_config("start_tx")
        auth_status = AuthorizationStatus.accepted
        if cfg:
            auth_map = {"Accepted": AuthorizationStatus.accepted, "Blocked": AuthorizationStatus.blocked,
                         "Expired": AuthorizationStatus.expired, "Invalid": AuthorizationStatus.invalid,
                         "ConcurrentTx": AuthorizationStatus.concurrent_tx}
            auth_status = auth_map.get(cfg.status, AuthorizationStatus.accepted)
            if cfg.behavior == "Delay" and cfg.delay > 0:
                await asyncio.sleep(cfg.delay)
            if cfg.behavior == "Drop":
                return None
        async with async_session() as db:
            if self._charge_point_db_id is None:
                cp = await cp_service.get_by_charge_box_id(db, self.id)
                if cp: self._charge_point_db_id = cp.id
            tx_id = await transaction_service.start_transaction(
                db=db, charge_point_id=self._charge_point_db_id or 0,
                connector_id=connector_id, id_tag=id_tag, meter_start=meter_start,
                start_timestamp=datetime.fromisoformat(timestamp))
            await cp_service.update_connector_status(db, self._charge_point_db_id or 0, connector_id, "Charging")
            await db.commit()
        return call_result.StartTransaction(transaction_id=tx_id, id_tag_info={"status": auth_status})

    @on(Action.stop_transaction)
    async def on_stop_transaction(self, transaction_id: int, timestamp: str, meter_stop: int, **kwargs):
        reason = kwargs.get("reason", "Local")
        logger.info(f"[{self.id}] StopTransaction: tx={transaction_id}, meter_stop={meter_stop}, reason={reason}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="StopTransaction (CALL)",
                            payload={"transaction_id": transaction_id, "meter_stop": meter_stop, "reason": reason, "timestamp": timestamp, **kwargs}))
        cfg = handler_config.get_config("stop_tx")
        if cfg:
            if cfg.behavior == "Delay" and cfg.delay > 0:
                await asyncio.sleep(cfg.delay)
            if cfg.behavior == "Drop":
                return None
        async with async_session() as db:
            await transaction_service.stop_transaction(db=db, transaction_id=transaction_id, meter_stop=meter_stop,
                                                        end_timestamp=datetime.fromisoformat(timestamp), stop_reason=reason)
            tx = await transaction_service.get_by_transaction_id(db, transaction_id)
            if tx and self._charge_point_db_id:
                await cp_service.update_connector_status(db, self._charge_point_db_id, tx.connector_id, "Available")
            await db.commit()
        return call_result.StopTransaction()

    @on(Action.meter_values)
    async def on_meter_values(self, connector_id: int, meter_value: list, **kwargs):
        transaction_id = kwargs.get("transaction_id")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="MeterValues (CALL)",
                            payload={"connector_id": connector_id, "transaction_id": transaction_id, "samples": len(meter_value),
                                      "values": [{sv.get("measurand", "?"): sv.get("value", "?") for sv in s.get("sampledValue", [])} for s in meter_value]}))
        async with async_session() as db:
            for sample in meter_value:
                await transaction_service.add_meter_value(db=db, transaction_id=transaction_id or 0,
                                                           connector_id=connector_id, timestamp=datetime.fromisoformat(sample["timestamp"]), value=sample)
            await db.commit()
        return call_result.MeterValues()

    @on(Action.status_notification)
    async def on_status_notification(self, connector_id: int, error_code: str, status: str, **kwargs):
        logger.info(f"[{self.id}] StatusNotification: connector={connector_id}, status={status}, error={error_code}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="StatusNotification (CALL)",
                            payload={"connector_id": connector_id, "status": status, "error_code": error_code, **kwargs}))
        async with async_session() as db:
            if self._charge_point_db_id is None:
                cp = await cp_service.get_by_charge_box_id(db, self.id)
                if cp: self._charge_point_db_id = cp.id
            if self._charge_point_db_id:
                await cp_service.update_connector_status(db, self._charge_point_db_id, connector_id, status, error_code)
            await db.commit()
        return call_result.StatusNotification()

    @on(Action.data_transfer)
    async def on_data_transfer(self, vendor_id: str, **kwargs):
        logger.info(f"[{self.id}] DataTransfer: vendor={vendor_id}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="DataTransfer (CALL)",
                            payload={"vendor_id": vendor_id, **kwargs}))
        return call_result.DataTransfer(status="Accepted")

    @on(Action.diagnostics_status_notification)
    async def on_diagnostics_status_notification(self, status: str):
        logger.info(f"[{self.id}] DiagnosticsStatusNotification: status={status}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="DiagnosticsStatusNotification (CALL)", payload={"status": status}))
        return call_result.DiagnosticsStatusNotification()

    @on(Action.firmware_status_notification)
    async def on_firmware_status_notification(self, status: str):
        logger.info(f"[{self.id}] FirmwareStatusNotification: status={status}")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="FirmwareStatusNotification (CALL)", payload={"status": status}))
        return call_result.FirmwareStatusNotification()

    # ==================== 远程命令 ====================

    async def send_reset(self, reset_type: str = "Soft") -> str:
        from ocpp.v16.enums import ResetType as RT
        req_type = RT.soft if reset_type.lower() == "soft" else RT.hard
        resp: call_result.Reset = await self.call(call.Reset(type=req_type))
        return resp.status

    async def send_remote_start(self, id_tag: str, connector_id: int = 1) -> str:
        resp: call_result.RemoteStartTransaction = await self.call(call.RemoteStartTransaction(id_tag=id_tag, connector_id=connector_id))
        return resp.status

    async def send_remote_stop(self, transaction_id: int) -> str:
        resp: call_result.RemoteStopTransaction = await self.call(call.RemoteStopTransaction(transaction_id=transaction_id))
        return resp.status

    async def send_change_configuration(self, key: str, value: str) -> str:
        resp: call_result.ChangeConfiguration = await self.call(call.ChangeConfiguration(key=key, value=value))
        return resp.status

    async def send_get_configuration(self, key: list[str] = None) -> call_result.GetConfiguration:
        return await self.call(call.GetConfiguration(key=key or []))

    async def send_clear_cache(self) -> str:
        resp: call_result.ClearCache = await self.call(call.ClearCache())
        return resp.status

    async def send_unlock_connector(self, connector_id: int) -> str:
        resp: call_result.UnlockConnector = await self.call(call.UnlockConnector(connector_id=connector_id))
        return resp.status

    async def send_trigger_message(self, requested_message: str, connector_id: int = None):
        from ocpp.v16.enums import MessageTrigger
        trigger_map = {"BootNotification": MessageTrigger.boot_notification, "DiagnosticsStatusNotification": MessageTrigger.diagnostics_status_notification,
                        "FirmwareStatusNotification": MessageTrigger.firmware_status_notification, "Heartbeat": MessageTrigger.heartbeat,
                        "MeterValues": MessageTrigger.meter_values, "StatusNotification": MessageTrigger.status_notification}
        trigger = trigger_map.get(requested_message, MessageTrigger.heartbeat)
        try:
            await asyncio.wait_for(self.call(call.TriggerMessage(requested_message=trigger, connector_id=connector_id)), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(f"[{self.id}] TriggerMessage timeout")

    async def send_update_firmware(self, location: str, retrieve_date: str, retries: int = 1, retry_interval: int = 60) -> str:
        await self.call(call.UpdateFirmware(location=location, retrieve_date=retrieve_date, retries=retries, retry_interval=retry_interval))
        return "Accepted"

    async def send_get_diagnostics(self, location: str, retries: int = 1, retry_interval: int = 60, start_time: str = None, stop_time: str = None) -> call_result.GetDiagnostics:
        return await self.call(call.GetDiagnostics(location=location, retries=retries, retry_interval=retry_interval, start_time=start_time, stop_time=stop_time))

    async def send_set_charging_profile(self, connector_id: int, cs_charging_profiles: dict) -> str:
        resp: call_result.SetChargingProfile = await self.call(call.SetChargingProfile(connector_id=connector_id, cs_charging_profiles=cs_charging_profiles))
        return resp.status

    async def send_clear_charging_profile(self, connector_id: int = None, charging_profile_purpose: str = None, stack_level: int = None, id_: int = None) -> str:
        from ocpp.v16.enums import ChargingProfilePurposeType
        kwargs = {}
        if id_ is not None: kwargs["id"] = id_
        if connector_id is not None: kwargs["connector_id"] = connector_id
        if charging_profile_purpose is not None:
            purpose_map = {"ChargePointMaxProfile": ChargingProfilePurposeType.charge_point_max_profile,
                           "TxDefaultProfile": ChargingProfilePurposeType.tx_default_profile, "TxProfile": ChargingProfilePurposeType.tx_profile}
            kwargs["charging_profile_purpose"] = purpose_map.get(charging_profile_purpose, ChargingProfilePurposeType.tx_default_profile)
        if stack_level is not None: kwargs["stack_level"] = stack_level
        resp: call_result.ClearChargingProfile = await self.call(call.ClearChargingProfile(**kwargs))
        return resp.status

    async def send_get_composite_schedule(self, connector_id: int, duration: int, charging_rate_unit: str = "A") -> call_result.GetCompositeSchedule:
        from ocpp.v16.enums import ChargingRateUnitType
        unit = ChargingRateUnitType.a if charging_rate_unit == "A" else ChargingRateUnitType.w
        return await self.call(call.GetCompositeSchedule(connector_id=connector_id, duration=duration, charging_rate_unit=unit))

    async def send_get_local_list_version(self) -> call_result.GetLocalListVersion:
        return await self.call(call.GetLocalListVersion())

    async def send_send_local_list(self, list_version: int, update_type: str, local_authorization_list: list = None) -> call_result.SendLocalList:
        from ocpp.v16.enums import UpdateType
        utype = UpdateType.differential if update_type == "Differential" else UpdateType.full
        kwargs = {"list_version": list_version, "update_type": utype}
        if local_authorization_list: kwargs["local_authorization_list"] = local_authorization_list
        return await self.call(call.SendLocalList(**kwargs))

    async def send_cancel_reservation(self, reservation_id: int) -> str:
        resp: call_result.CancelReservation = await self.call(call.CancelReservation(reservation_id=reservation_id))
        return resp.status

    async def send_reserve_now(self, connector_id: int, expiry_date: str, id_tag: str, reservation_id: int = None, parent_id_tag: str = None) -> str:
        if expiry_date and not expiry_date.endswith('Z'):
            if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$', expiry_date):
                expiry_date = expiry_date + ':00Z'
            elif not expiry_date.endswith('Z'):
                expiry_date = expiry_date + 'Z'
        kwargs: dict = {"connector_id": connector_id, "expiry_date": expiry_date, "id_tag": id_tag,
                         "reservation_id": reservation_id if reservation_id else random.randint(10000, 99999)}
        if parent_id_tag is not None:
            kwargs["parent_id_tag"] = parent_id_tag
        resp: call_result.ReserveNow = await self.call(call.ReserveNow(**kwargs))
        return resp.status

    # ==================== 连接管理 ====================

    async def on_disconnect(self):
        logger.info(f"[{self.id}] Disconnected")
        publish(OcppMessage(charge_box_id=self.id, direction="IN", action="断开连接", payload={}))
        async with async_session() as db:
            await cp_service.set_online(db, self.id, online=False)
            await db.commit()
