"""OCPP 1.6 CSMS —— 统一入口

启动：
    python main.py

访问：
    Web UI:  http://localhost:8000
    API 文档: http://localhost:8000/docs
    充电桩连接: ws://localhost:9000/{charge_box_id}
"""

import sys
import asyncio
import logging

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    # Win7 兼容：强制 SelectorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import uvicorn

from config import settings, VERSION
from models.database import init_db
from web.app import app
from web.routes import *  # noqa
from web.api import *     # noqa
from web.sse import *     # noqa
from ocpp_server.server import start_ws_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


async def _check_update_on_startup():
    """启动时后台静默检测更新（GitHub → Gitee 依次尝试）"""
    try:
        import httpx
        from config import VERSION
        sources = [
            ("GitHub", "https://api.github.com/repos/littlejazzcat/OCPP1.6_Server/releases/latest",
             {"Accept": "application/vnd.github+json"}),
            ("Gitee", "https://gitee.com/api/v5/repos/littlejazzcat/OCPP1.6_Server/releases/latest", {}),
        ]
        for name, url, headers in sources:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        latest = data["tag_name"]
                        if latest != VERSION:
                            logger.info(f"[{name}] New release: {latest} (current: {VERSION})")
                        return
            except Exception:
                continue
    except Exception:
        pass


async def main():
    logger.info("=" * 50)
    logger.info(f"OCPP 1.6 CSMS Server v{VERSION}")
    logger.info(f"  WebSocket: {settings.ws_host}:{settings.ws_port}")
    logger.info(f"  Web UI:    http://{settings.web_host}:{settings.web_port}")
    logger.info(f"  API Docs:  http://localhost:{settings.web_port}/docs")
    logger.info("=" * 50)

    await init_db()
    logger.info("Database initialized ✓")

    # 后台检测更新
    asyncio.create_task(_check_update_on_startup())

    # 启动 WebSocket 服务器
    async def _ws_with_log():
        try:
            await start_ws_server()
        except Exception as e:
            logger.error(f"WebSocket server failed: {e}", exc_info=True)
    ws_task = asyncio.create_task(_ws_with_log())

    # 自动打开浏览器
    import webbrowser
    webbrowser.open(f"http://localhost:{settings.web_port}")

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
