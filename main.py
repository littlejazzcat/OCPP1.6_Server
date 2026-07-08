"""OCPP 1.6 CSMS —— 统一入口

启动：
    python main.py

访问：
    Web UI:  http://localhost:8000
    API 文档: http://localhost:8000/docs
    充电桩连接: ws://localhost:9000/{charge_box_id}
"""

import sys

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import logging

import uvicorn

from config import settings
from models.database import init_db
from web.app import app
from web.routes import *  # noqa: 注册页面路由
from web.api import *     # noqa: 注册 API
from web.sse import *     # noqa: 注册 SSE
from ocpp_server.server import start_ws_server

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


async def main():
    logger.info("=" * 50)
    logger.info("OCPP 1.6 CSMS Server starting...")
    logger.info(f"  WebSocket: {settings.ws_host}:{settings.ws_port}")
    logger.info(f"  Web UI:    http://{settings.web_host}:{settings.web_port}")
    logger.info(f"  API Docs:  http://localhost:{settings.web_port}/docs")
    logger.info("=" * 50)

    # 初始化数据库
    await init_db()
    logger.info("Database initialized ✓")

    # 启动 WebSocket 服务器（后台任务）
    ws_task = asyncio.create_task(start_ws_server())

    # 启动 FastAPI Web 服务器
    config = uvicorn.Config(
        app,
        host=settings.web_host,
        port=settings.web_port,
        log_level="info",
        timeout_keep_alive=5,
        use_colors=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except OSError as e:
        if "address already in use" in str(e).lower() or "仅允许" in str(e):
            print(f"\n端口被占用，请检查 {settings.ws_port} 或 {settings.web_port} 是否已被其他程序使用\n")
        else:
            raise
        sys.exit(1)
