"""数据表定义"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ChargePoint(Base):
    __tablename__ = "charge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charge_box_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="充电桩唯一标识")
    vendor: Mapped[Optional[str]] = mapped_column(String(128), comment="厂商")
    model: Mapped[Optional[str]] = mapped_column(String(128), comment="型号")
    serial_number: Mapped[Optional[str]] = mapped_column(String(64), comment="序列号")
    firmware_version: Mapped[Optional[str]] = mapped_column(String(64), comment="固件版本")
    iccid: Mapped[Optional[str]] = mapped_column(String(32), comment="SIM 卡 ICCID")
    imsi: Mapped[Optional[str]] = mapped_column(String(32), comment="SIM 卡 IMSI")
    meter_type: Mapped[Optional[str]] = mapped_column(String(64), comment="电表类型")
    online: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否在线")
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最后心跳时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    connectors: Mapped[list["Connector"]] = relationship(back_populates="charge_point", cascade="all, delete-orphan")


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charge_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("charge_points.id"))
    connector_id: Mapped[int] = mapped_column(Integer, comment="连接器编号（0=整桩, 1/2/3...=枪号）")
    status: Mapped[str] = mapped_column(String(32), default="Unavailable", comment="状态：Available/Preparing/Charging/...")
    error_code: Mapped[str] = mapped_column(String(32), default="NoError")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    charge_point: Mapped["ChargePoint"] = relationship(back_populates="connectors")


class OcppTag(Base):
    __tablename__ = "ocpp_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_tag: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="RFID 标签/用户 ID")
    parent_id_tag: Mapped[Optional[str]] = mapped_column(String(64), comment="父标签（集团卡场景）")
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="过期时间")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否禁用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, comment="OCPP 事务 ID")
    charge_point_id: Mapped[int] = mapped_column(Integer, ForeignKey("charge_points.id"))
    connector_id: Mapped[int] = mapped_column(Integer, comment="连接器编号")
    id_tag: Mapped[str] = mapped_column(String(64), comment="启动事务的标签")
    start_timestamp: Mapped[datetime] = mapped_column(DateTime, comment="启动时间")
    end_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="结束时间")
    meter_start: Mapped[int] = mapped_column(Integer, default=0, comment="起始电表读数(Wh)")
    meter_stop: Mapped[Optional[int]] = mapped_column(Integer, comment="结束电表读数(Wh)")
    stop_reason: Mapped[Optional[str]] = mapped_column(String(64), comment="停止原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    meter_values: Mapped[list["MeterValue"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class MeterValue(Base):
    __tablename__ = "meter_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.transaction_id"))
    connector_id: Mapped[int] = mapped_column(Integer, comment="连接器编号")
    timestamp: Mapped[datetime] = mapped_column(DateTime, comment="采样时间")
    value: Mapped[dict] = mapped_column(JSON, comment="sampledValue JSON 原文")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transaction: Mapped["Transaction"] = relationship(back_populates="meter_values")
