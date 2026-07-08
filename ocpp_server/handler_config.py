"""Handler 运行时配置 —— Web UI 设置通过 API 同步到此模块"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HandlerConfig:
    status: str = "Accepted"
    behavior: str = "Normal"
    delay: int = 0
    interval: int = 86400


# 全局 handler 配置（action → HandlerConfig）
_configs: dict[str, HandlerConfig] = {
    "authorize": HandlerConfig(status="Accepted"),
    "boot": HandlerConfig(status="Accepted"),
    "start_tx": HandlerConfig(status="Accepted"),
    "stop_tx": HandlerConfig(status="Accepted"),
    "data_transfer": HandlerConfig(status="Accepted"),
}


def get_config(action: str) -> Optional[HandlerConfig]:
    return _configs.get(action)


def set_config(action: str, config: dict):
    existing = _configs.get(action, HandlerConfig())
    existing.status = config.get("status", existing.status)
    existing.behavior = config.get("behavior", existing.behavior)
    existing.delay = config.get("delay", existing.delay)
    existing.interval = config.get("interval", existing.interval)
    _configs[action] = existing


def get_all_configs() -> dict:
    return {k: {"status": v.status, "behavior": v.behavior, "delay": v.delay, "interval": v.interval}
            for k, v in _configs.items()}
