"""SSE 实时推送 —— 极简 StreamingResponse 实现"""

import asyncio
import json
from dataclasses import asdict

from fastapi import Request
from fastapi.responses import StreamingResponse

from .app import app
from ocpp_server.server import get_online_charge_points
from ocpp_server.message_bus import _message_queue, OcppMessage


@app.get("/sse/status")
async def sse_status(request: Request):
    async def gen():
        try:
            current = set(get_online_charge_points())
            yield f"event: status_update\ndata: {json.dumps({'online': list(current), 'count': len(current)})}\n\n"
            last_online = current
            while True:
                await asyncio.sleep(1)
                if await request.is_disconnected():
                    break
                current = set(get_online_charge_points())
                if current != last_online:
                    yield f"event: status_update\ndata: {json.dumps({'online': list(current), 'count': len(current)})}\n\n"
                    last_online = current
        except asyncio.CancelledError:
            pass

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/sse/messages")
async def sse_messages(request: Request):
    async def gen():
        try:
            batch = _drain_queue()
            if batch:
                yield f"event: ocpp_messages\ndata: {json.dumps([asdict(m) for m in batch])}\n\n"
            else:
                yield "event: init\ndata: {}\n\n"
            while True:
                await asyncio.sleep(0.3)
                if await request.is_disconnected():
                    break
                batch = _drain_queue()
                if batch:
                    yield f"event: ocpp_messages\ndata: {json.dumps([asdict(m) for m in batch])}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


def _drain_queue() -> list[OcppMessage]:
    messages = []
    try:
        while True:
            messages.append(_message_queue.get_nowait())
    except asyncio.QueueEmpty:
        pass
    return messages
