"""WebSocket 服务器：接受充电桩连接"""

import asyncio
import logging

import websockets

from config import settings
from .charge_point import ChargePointHandler

logger = logging.getLogger("ocpp_server")

# 全局连接池：{charge_box_id: ChargePointHandler}
connections: dict[str, ChargePointHandler] = {}


async def on_connect(connection: websockets.ServerConnection):
    """每个充电桩连接的处理入口"""
    charge_point_id = connection.request.path.strip("/")
    logger.info(f"[+] Charge point connected: {charge_point_id}")

    handler = ChargePointHandler(charge_point_id, connection)
    connections[charge_point_id] = handler

    try:
        await handler.start()
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[-] Charge point disconnected: {charge_point_id}")
    finally:
        await handler.on_disconnect()
        connections.pop(charge_point_id, None)


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
    )
    logger.info("WebSocket server started ✓")
    await server.wait_closed()


def get_connection(charge_box_id: str) -> ChargePointHandler | None:
    """获取充电桩连接（供 Web 层调用）"""
    return connections.get(charge_box_id)


def get_online_charge_points() -> list[str]:
    """获取当前在线的充电桩列表"""
    return list(connections.keys())
