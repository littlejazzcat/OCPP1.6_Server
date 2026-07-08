"""REST API 端点"""

import asyncio

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .app import app
from models.database import async_session, get_session
from models.schema import ChargePoint, Transaction, OcppTag
from services import cp_service, auth_service, transaction_service
from ocpp_server.server import get_connection, get_online_charge_points
from ocpp_server.message_bus import get_history_page
from ocpp_server import handler_config


# ==================== 充电桩 API ====================

@app.get("/api/charge-points")
async def api_list_charge_points():
    async with async_session() as db:
        cps = await cp_service.list_all(db)
    return [
        {
            "id": cp.id,
            "charge_box_id": cp.charge_box_id,
            "vendor": cp.vendor,
            "model": cp.model,
            "online": cp.online,
            "last_heartbeat": cp.last_heartbeat.isoformat() if cp.last_heartbeat else None,
        }
        for cp in cps
    ]


@app.get("/api/charge-points/online")
async def api_online_charge_points():
    return {"online": get_online_charge_points()}


# ==================== 远程操作 API ====================

@app.post("/api/charge-points/{charge_box_id}/reset")
async def api_reset(charge_box_id: str, reset_type: str = "Soft"):
    """向指定充电桩下发 Reset 命令"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_reset(reset_type)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/remote-start")
async def api_remote_start(charge_box_id: str, id_tag: str, connector_id: int = 1):
    """远程启动充电"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_remote_start(id_tag, connector_id)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/remote-stop")
async def api_remote_stop(charge_box_id: str, transaction_id: int):
    """远程停止充电"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_remote_stop(transaction_id)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/change-config")
async def api_change_config(charge_box_id: str, key: str, value: str):
    """修改充电桩配置"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_change_configuration(key, value)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/clear-cache")
async def api_clear_cache(charge_box_id: str):
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_clear_cache()
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/unlock")
async def api_unlock(charge_box_id: str, connector_id: int):
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_unlock_connector(connector_id)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/get-config")
async def api_get_config(charge_box_id: str):
    """读取充电桩配置"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    result = await handler.send_get_configuration()
    return {
        "configuration_key": result.configuration_key,
        "unknown_key": result.unknown_key,
    }


@app.post("/api/charge-points/{charge_box_id}/update-firmware")
async def api_update_firmware(
    charge_box_id: str, location: str, retrieve_date: str,
    retries: int = 1, retry_interval: int = 60
):
    """下发固件更新"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_update_firmware(location, retrieve_date, retries, retry_interval)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/get-diagnostics")
async def api_get_diagnostics(
    charge_box_id: str, location: str,
    retries: int = 1, retry_interval: int = 60,
    start_time: str = None, stop_time: str = None
):
    """请求诊断文件上传"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    result = await handler.send_get_diagnostics(location, retries, retry_interval, start_time, stop_time)
    return {"file_name": result.file_name}


@app.post("/api/charge-points/{charge_box_id}/set-charging-profile")
async def api_set_charging_profile(
    charge_box_id: str,
    connector_id: int,
    charging_profile_id: int,
    stack_level: int,
    charging_profile_purpose: str = "TxProfile",
    charging_profile_kind: str = "Absolute",
    charging_rate_unit: str = "A",
    limit: float = 16.0,
    start_period: int = 0,
    duration: int = None,
    number_phases: int = None,
):
    """设置充电曲线"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    
    schedule_period = {"start_period": start_period, "limit": limit}
    if number_phases is not None:
        schedule_period["number_phases"] = number_phases
    
    charging_schedule = {
        "charging_rate_unit": charging_rate_unit,
        "charging_schedule_period": [schedule_period],
    }
    if duration is not None:
        charging_schedule["duration"] = duration
    
    cs_charging_profiles = {
        "charging_profile_id": charging_profile_id,
        "stack_level": stack_level,
        "charging_profile_purpose": charging_profile_purpose,
        "charging_profile_kind": charging_profile_kind,
        "charging_schedule": charging_schedule,
    }
    
    status = await handler.send_set_charging_profile(connector_id, cs_charging_profiles)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/clear-charging-profile")
async def api_clear_charging_profile(
    charge_box_id: str,
    connector_id: int = None,
    charging_profile_purpose: str = None,
    stack_level: int = None,
    id: int = None,
):
    """清除充电曲线"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_clear_charging_profile(
        connector_id=connector_id,
        charging_profile_purpose=charging_profile_purpose,
        stack_level=stack_level,
        id_=id,
    )
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/get-composite-schedule")
async def api_get_composite_schedule(
    charge_box_id: str, connector_id: int, duration: int,
    charging_rate_unit: str = "A"
):
    """获取组合充电计划"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    result = await handler.send_get_composite_schedule(connector_id, duration, charging_rate_unit)
    return {
        "status": result.status,
        "connector_id": result.connector_id,
        "schedule_start": result.schedule_start,
        "charging_schedule": result.charging_schedule,
    }


@app.post("/api/charge-points/{charge_box_id}/get-local-list")
async def api_get_local_list(charge_box_id: str):
    """获取本地授权列表版本"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    result = await handler.send_get_local_list_version()
    return {"list_version": result.list_version}


@app.post("/api/charge-points/{charge_box_id}/send-local-list")
async def api_send_local_list(
    charge_box_id: str, list_version: int, update_type: str
):
    """发送本地授权列表"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    result = await handler.send_send_local_list(list_version, update_type)
    return {"status": result.status}


@app.post("/api/charge-points/{charge_box_id}/trigger")
async def api_trigger(
    charge_box_id: str, requested_message: str, connector_id: int = None
):
    """触发充电桩上报指定消息"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    try:
        await handler.send_trigger_message(requested_message, connector_id)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="TriggerMessage timeout: charge point not responding")
    return {"status": "Accepted"}


@app.post("/api/charge-points/{charge_box_id}/cancel-reservation")
async def api_cancel_reservation(charge_box_id: str, reservation_id: int):
    """取消预约"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_cancel_reservation(reservation_id)
    return {"status": status}


@app.post("/api/charge-points/{charge_box_id}/reserve-now")
async def api_reserve_now(
    charge_box_id: str, connector_id: int, expiry_date: str,
    id_tag: str, reservation_id: int = None, parent_id_tag: str = None
):
    """预约充电桩"""
    handler = get_connection(charge_box_id)
    if handler is None:
        raise HTTPException(status_code=404, detail="Charge point not online")
    status = await handler.send_reserve_now(
        connector_id, expiry_date, id_tag, reservation_id, parent_id_tag
    )
    return {"status": status}


# ==================== 交易 API ====================

@app.get("/api/transactions")
async def api_list_transactions(limit: int = 50):
    async with async_session() as db:
        txs = await transaction_service.list_transactions(db, limit=limit)
    return [
        {
            "transaction_id": tx.transaction_id,
            "charge_point_id": tx.charge_point_id,
            "connector_id": tx.connector_id,
            "id_tag": tx.id_tag,
            "start_timestamp": tx.start_timestamp.isoformat(),
            "end_timestamp": tx.end_timestamp.isoformat() if tx.end_timestamp else None,
            "meter_start": tx.meter_start,
            "meter_stop": tx.meter_stop,
            "stop_reason": tx.stop_reason,
        }
        for tx in txs
    ]


# ==================== 标签 API ====================

@app.get("/api/tags")
async def api_list_tags():
    async with async_session() as db:
        tags = await auth_service.list_tags(db)
    return [
        {
            "id_tag": tag.id_tag,
            "parent_id_tag": tag.parent_id_tag,
            "expiry_date": tag.expiry_date.isoformat() if tag.expiry_date else None,
            "blocked": tag.blocked,
        }
        for tag in tags
    ]


@app.post("/api/tags")
async def api_create_tag(id_tag: str, parent_id_tag: str = None):
    async with async_session() as db:
        tag = await auth_service.create_tag(db, id_tag, parent_id_tag)
        await db.commit()
    return {"id_tag": tag.id_tag}


@app.delete("/api/tags/{id_tag}")
async def api_delete_tag(id_tag: str):
    async with async_session() as db:
        ok = await auth_service.delete_tag(db, id_tag)
        await db.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"deleted": True}


@app.post("/api/tags/{id_tag}/block")
async def api_block_tag(id_tag: str, blocked: bool = True):
    async with async_session() as db:
        await auth_service.set_blocked(db, id_tag, blocked)
        await db.commit()
    return {"blocked": blocked}


# ==================== 报文 API ====================

@app.get("/api/messages")
async def api_messages(offset: int = 0, limit: int = 10):
    """分页获取历史报文"""
    page = get_history_page(offset=offset, limit=limit)
    return {
        "messages": [
            {
                "seq": m.seq,
                "charge_box_id": m.charge_box_id,
                "direction": m.direction,
                "action": m.action,
                "payload": m.payload,
                "timestamp": m.timestamp,
                "msg_type": m.msg_type,
            }
            for m in page["messages"]
        ],
        "total": page["total"],
        "has_newer": page["has_newer"],
        "has_older": page["has_older"],
    }


@app.delete("/api/messages")
async def api_clear_messages():
    """清除所有报文历史"""
    from ocpp_server.message_bus import clear_history
    clear_history()
    return {"cleared": True}


@app.delete("/api/transactions")
async def api_clear_transactions():
    """清除所有交易记录"""
    from models.schema import Transaction, MeterValue
    async with async_session() as db:
        from sqlalchemy import delete
        await db.execute(delete(MeterValue))
        await db.execute(delete(Transaction))
        await db.commit()
    return {"cleared": True}


@app.delete("/api/charge-points")
async def api_clear_charge_points():
    """清除所有充电桩记录"""
    from models.schema import ChargePoint, Connector, Transaction, MeterValue
    async with async_session() as db:
        from sqlalchemy import delete
        await db.execute(delete(MeterValue))
        await db.execute(delete(Transaction))
        await db.execute(delete(Connector))
        await db.execute(delete(ChargePoint))
        await db.commit()
    return {"cleared": True}


# ==================== Handler 配置 API ====================

@app.get("/api/handler-config")
async def api_get_handler_config():
    return handler_config.get_all_configs()


@app.post("/api/handler-config/{action}")
async def api_set_handler_config(action: str, status: str = None, behavior: str = None, delay: int = 0, interval: int = None):
    config = {}
    if status is not None:
        config["status"] = status
    if behavior is not None:
        config["behavior"] = behavior
        config["delay"] = delay
    if interval is not None:
        config["interval"] = interval
    handler_config.set_config(action, config)
    return handler_config.get_all_configs()
