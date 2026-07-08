"""FastAPI 应用实例"""

import time
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="OCPP 1.6 CSMS", version="0.1.0")
logger = logging.getLogger("web")


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    # 只记录非 SSE 请求（SSE 请求不会结束）
    if request.url.path.startswith("/sse/"):
        logger.debug(f"{request.method} {request.url.path} [SSE]")
    else:
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.0f}ms)")
    return response


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    """防止浏览器缓存页面，确保切页总是重新请求"""
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# 静态文件
static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
