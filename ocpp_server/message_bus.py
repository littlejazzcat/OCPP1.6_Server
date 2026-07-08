"""共享消息通道 —— 用于在 OCPP 层和 Web 层之间传递实时报文"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class OcppMessage:
    """一条 OCPP 报文记录"""
    charge_box_id: str
    direction: Literal["IN", "OUT"]  # IN=收到充电桩消息, OUT=发给充电桩
    action: str                      # 消息类型
    payload: dict = field(default_factory=dict)
    seq: int = 0                     # 全局递增序号
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3])
    msg_type: int = 0                # 2=CALL, 3=CALLRESULT, 4=CALLERROR, 0=其他


# 全局消息队列（SSE 端轮询 drain）
_message_queue: asyncio.Queue[OcppMessage] = asyncio.Queue(maxsize=500)

# 历史消息缓存（不设上限，持久到重启清空）
_message_history: list[OcppMessage] = []
_seq_counter: int = 0


def publish(msg: OcppMessage):
    """发布一条报文（OCPP 层调用）"""
    global _seq_counter
    _seq_counter += 1
    msg.seq = _seq_counter
    _message_history.append(msg)

    # 放队列（非阻塞，满了丢弃最旧的）
    try:
        _message_queue.put_nowait(msg)
    except asyncio.QueueFull:
        try:
            _message_queue.get_nowait()
            _message_queue.put_nowait(msg)
        except (asyncio.QueueEmpty, asyncio.QueueFull):
            pass


def get_history_page(offset: int = 0, limit: int = 10) -> dict:
    """分页获取历史消息（从旧到新排序）"""
    total = len(_message_history)
    start = max(0, total - offset - limit)
    end = total - offset
    page = _message_history[start:end]
    return {
        "messages": page,
        "total": total,
        "has_newer": offset > 0,
        "has_older": end < total,
    }


def clear_history():
    """清除所有历史消息"""
    global _seq_counter
    _message_history.clear()
    _seq_counter = 0
    # 同时清空队列
    while not _message_queue.empty():
        try:
            _message_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
