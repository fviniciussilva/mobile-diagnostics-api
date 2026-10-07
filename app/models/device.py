import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class DevicePlatform(PyEnum):
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


class DeviceStatus(PyEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNAUTHORIZED = "unauthorized"


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial = Column(String(255), unique=True, nullable=False, index=True)
    platform = Column(Enum(DevicePlatform), nullable=False, default=DevicePlatform.UNKNOWN)
    model = Column(String(255))
    manufacturer = Column(String(255))
    android_version = Column(String(50))
    ios_version = Column(String(50))
    sdk_version = Column(String(50))
    imei = Column(String(50), nullable=True, index=True)
    imei2 = Column(String(50), nullable=True)
    serial_number = Column(String(255), nullable=True)
    battery_level = Column(Integer, nullable=True)
    battery_health = Column(String(50), nullable=True)
    storage_total = Column(Integer, nullable=True)  # bytes
    storage_free = Column(Integer, nullable=True)  # bytes
    is_rooted = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)
    status = Column(Enum(DeviceStatus), default=DeviceStatus.DISCONNECTED)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    diagnostics = relationship("Diagnostic", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_devices_platform_status", "platform", "status"),
        Index("ix_devices_last_seen", "last_seen"),
    )


class DiagnosticType(PyEnum):
    BASIC_INFO = "basic_info"
    BATTERY = "battery"
    STORAGE = "storage"
    NETWORK = "network"
    SECURITY = "security"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    FULL = "full"
    BACKUP = "backup"
    IMEI_CHECK = "imei_check"


class DiagnosticStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(DiagnosticType), nullable=False)
    status = Column(Enum(DiagnosticStatus), default=DiagnosticStatus.PENDING)
    result = Column(Text, nullable=True)  # JSON string
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    device = relationship("Device", back_populates="diagnostics")

    __table_args__ = (
        Index("ix_diagnostics_device_type", "device_id", "type"),
        Index("ix_diagnostics_status_created", "status", "created_at"),
    )
