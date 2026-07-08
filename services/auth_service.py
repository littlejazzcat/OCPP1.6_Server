"""授权管理服务"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schema import OcppTag


async def authorize(db: AsyncSession, id_tag: str) -> str:
    """
    验证 RFID 标签 / 用户 ID
    测试平台默认策略：未知标签自动注册并放行
    返回: "Accepted" / "Blocked" / "Expired" / "Invalid"
    """
    result = await db.execute(
        select(OcppTag).where(OcppTag.id_tag == id_tag)
    )
    tag = result.scalar_one_or_none()

    if tag is None:
        # 测试平台：自动注册新标签
        tag = OcppTag(id_tag=id_tag)
        db.add(tag)
        await db.flush()
        return "Accepted"

    if tag.blocked:
        return "Blocked"

    if tag.expiry_date and tag.expiry_date < datetime.now(tz=timezone.utc):
        return "Expired"

    return "Accepted"


async def list_tags(db: AsyncSession) -> list[OcppTag]:
    result = await db.execute(select(OcppTag).order_by(OcppTag.created_at.desc()))
    return list(result.scalars().all())


async def create_tag(
    db: AsyncSession,
    id_tag: str,
    parent_id_tag: str = None,
    expiry_date: datetime = None,
) -> OcppTag:
    tag = OcppTag(
        id_tag=id_tag,
        parent_id_tag=parent_id_tag,
        expiry_date=expiry_date,
    )
    db.add(tag)
    await db.flush()
    return tag


async def set_blocked(db: AsyncSession, id_tag: str, blocked: bool):
    result = await db.execute(
        select(OcppTag).where(OcppTag.id_tag == id_tag)
    )
    tag = result.scalar_one_or_none()
    if tag:
        tag.blocked = blocked
        await db.flush()


async def delete_tag(db: AsyncSession, id_tag: str) -> bool:
    result = await db.execute(
        select(OcppTag).where(OcppTag.id_tag == id_tag)
    )
    tag = result.scalar_one_or_none()
    if tag:
        await db.delete(tag)
        await db.flush()
        return True
    return False
