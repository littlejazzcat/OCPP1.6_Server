"""充电桩管理服务"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schema import ChargePoint, Connector


async def register_or_update(
    db: AsyncSession,
    charge_box_id: str,
    vendor: str,
    model: str,
    serial_number: str = None,
    firmware_version: str = None,
    iccid: str = None,
    imsi: str = None,
    meter_type: str = None,
):
    """充电桩启动注册，存在则更新，不存在则创建"""
    result = await db.execute(
        select(ChargePoint).where(ChargePoint.charge_box_id == charge_box_id)
    )
    cp = result.scalar_one_or_none()

    if cp is None:
        cp = ChargePoint(charge_box_id=charge_box_id)
        db.add(cp)

    cp.vendor = vendor
    cp.model = model
    cp.serial_number = serial_number
    cp.firmware_version = firmware_version
    cp.iccid = iccid
    cp.imsi = imsi
    cp.meter_type = meter_type
    cp.online = True
    cp.last_heartbeat = datetime.now(tz=timezone.utc)

    await db.flush()
    return cp


async def set_online(db: AsyncSession, charge_box_id: str, online: bool):
    result = await db.execute(
        select(ChargePoint).where(ChargePoint.charge_box_id == charge_box_id)
    )
    cp = result.scalar_one_or_none()
    if cp:
        cp.online = online
        await db.flush()


async def update_heartbeat(db: AsyncSession, charge_box_id: str):
    result = await db.execute(
        select(ChargePoint).where(ChargePoint.charge_box_id == charge_box_id)
    )
    cp = result.scalar_one_or_none()
    if cp:
        cp.last_heartbeat = datetime.now(tz=timezone.utc)
        cp.online = True
        await db.flush()


async def get_by_charge_box_id(db: AsyncSession, charge_box_id: str) -> ChargePoint | None:
    result = await db.execute(
        select(ChargePoint).where(ChargePoint.charge_box_id == charge_box_id)
    )
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession) -> list[ChargePoint]:
    result = await db.execute(select(ChargePoint).order_by(ChargePoint.created_at.desc()))
    return list(result.scalars().all())


async def update_connector_status(
    db: AsyncSession,
    charge_point_id: int,
    connector_id: int,
    status: str,
    error_code: str = "NoError",
):
    """更新连接器状态，不存在则创建"""
    result = await db.execute(
        select(Connector).where(
            Connector.charge_point_id == charge_point_id,
            Connector.connector_id == connector_id,
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        conn = Connector(
            charge_point_id=charge_point_id,
            connector_id=connector_id,
        )
        db.add(conn)
    conn.status = status
    conn.error_code = error_code
    await db.flush()
    return conn


async def get_connectors(db: AsyncSession, charge_point_id: int) -> list[Connector]:
    result = await db.execute(
        select(Connector).where(Connector.charge_point_id == charge_point_id)
    )
    return list(result.scalars().all())
