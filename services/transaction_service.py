"""事务管理服务"""

import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schema import Transaction, MeterValue


# 全局事务 ID 计数器（简单实现，生产环境可用数据库序列）
_tx_counter = random.randint(1, 99999)


async def start_transaction(
    db: AsyncSession,
    charge_point_id: int,
    connector_id: int,
    id_tag: str,
    meter_start: int,
    start_timestamp: datetime,
) -> int:
    """创建新事务，返回 transaction_id"""
    global _tx_counter
    _tx_counter += 1
    tx_id = _tx_counter

    tx = Transaction(
        transaction_id=tx_id,
        charge_point_id=charge_point_id,
        connector_id=connector_id,
        id_tag=id_tag,
        start_timestamp=start_timestamp,
        meter_start=meter_start,
    )
    db.add(tx)
    await db.flush()
    return tx_id


async def stop_transaction(
    db: AsyncSession,
    transaction_id: int,
    meter_stop: int,
    end_timestamp: datetime,
    stop_reason: str = None,
) -> bool:
    """终止事务"""
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        return False

    tx.meter_stop = meter_stop
    tx.end_timestamp = end_timestamp
    tx.stop_reason = stop_reason
    await db.flush()
    return True


async def add_meter_value(
    db: AsyncSession,
    transaction_id: int,
    connector_id: int,
    timestamp: datetime,
    value: dict,
):
    """存储电表采样数据"""
    mv = MeterValue(
        transaction_id=transaction_id,
        connector_id=connector_id,
        timestamp=timestamp,
        value=value,
    )
    db.add(mv)
    await db.flush()


async def list_transactions(
    db: AsyncSession,
    limit: int = 50,
    charge_point_id: int = None,
) -> list[Transaction]:
    """查询交易列表"""
    stmt = select(Transaction).order_by(Transaction.start_timestamp.desc())
    if charge_point_id:
        stmt = stmt.where(Transaction.charge_point_id == charge_point_id)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_transaction_id(db: AsyncSession, transaction_id: int) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
    return result.scalar_one_or_none()


async def get_meter_values(db: AsyncSession, transaction_id: int) -> list[MeterValue]:
    result = await db.execute(
        select(MeterValue)
        .where(MeterValue.transaction_id == transaction_id)
        .order_by(MeterValue.timestamp.asc())
    )
    return list(result.scalars().all())
