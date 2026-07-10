"""全局配置"""

from pydantic_settings import BaseSettings

# 当前版本号（发布时手动更新）
VERSION = "v1.0.1"


class Settings(BaseSettings):
    # WebSocket Server（充电桩连接）
    ws_host: str = "0.0.0.0"
    ws_port: int = 9000

    # Web Server（管理界面 + API）
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # 数据库
    database_url: str = "sqlite+aiosqlite:///ocpp_server.db"

    # OCPP 协议版本
    ocpp_subprotocols: list[str] = ["ocpp1.6"]

    # 默认心跳间隔（秒）
    default_heartbeat_interval: int = 60

    model_config = {"env_prefix": "OCPP_", "env_file": ".env"}


settings = Settings()
