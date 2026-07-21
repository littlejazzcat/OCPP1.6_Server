"""WebSocket 服务器：接受充电桩连接"""

import asyncio
import logging

import websockets

from config import settings
from .charge_point import ChargePointHandler

logger = logging.getLogger("ocpp_server")

# 全局连接池：{charge_box_id: ChargePointHandler}
connections: dict[str, ChargePointHandler] = {}
# 连接序号，用于竞态判断
_conn_seq: dict[str, int] = {}


async def on_connect(connection: websockets.ServerConnection):
    """每个充电桩连接的处理入口"""
    charge_point_id = connection.request.path.strip("/")

    # 分配连接序号
    seq = _conn_seq.get(charge_point_id, 0) + 1
    _conn_seq[charge_point_id] = seq

    logger.info(f"[+] Charge point connected: {charge_point_id} (#{seq})")

    # 连接建立即标记在线
    from models.database import async_session
    from services.cp_service import set_online as cp_set_online
    async with async_session() as db:
        await cp_set_online(db, charge_point_id, True)
        await db.commit()

    handler = ChargePointHandler(charge_point_id, connection)
    handler._conn_seq = seq
    connections[charge_point_id] = handler

    try:
        await handler.start()
    except websockets.exceptions.ConnectionClosed as e:
        reason = f"code={e.code}" if hasattr(e, 'code') else str(e)
        logger.info(f"[-] Charge point disconnected: {charge_point_id} (#{seq}, {reason})")
    finally:
        if handler._conn_seq == _conn_seq.get(charge_point_id):
            await handler.on_disconnect()
            connections.pop(charge_point_id, None)
        else:
            logger.info(f"[~] Charge point {charge_point_id} (#{seq}) already superseded, skip cleanup")


async def start_ws_server():
    """启动 WebSocket 服务器"""
    logger.info(
        f"WebSocket server starting on {settings.ws_host}:{settings.ws_port}"
    )
    server = await websockets.serve(
        on_connect,
        settings.ws_host,
        settings.ws_port,
        subprotocols=settings.ocpp_subprotocols,
        ping_interval=30,     # 发 ping 维持 NAT 保活
        ping_timeout=None,    # pong 超时不关连接
        close_timeout=5,
    )
    logger.info("WebSocket server started ✓")
    await server.wait_closed()


def get_connection(charge_box_id: str) -> ChargePointHandler | None:
    """获取充电桩连接（供 Web 层调用）"""
    return connections.get(charge_box_id)


def get_online_charge_points() -> list[str]:
    """获取当前在线的充电桩列表"""
    return list(connections.keys())
