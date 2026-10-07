import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DevicePlatform(str, Enum):
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNAUTHORIZED = "unauthorized"


class DiagnosticType(str, Enum):
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


class DiagnosticStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# Device schemas
class DeviceBase(BaseModel):
    serial: str = Field(..., min_length=1, max_length=255)
    platform: DevicePlatform = DevicePlatform.UNKNOWN
    model: str | None = Field(None, max_length=255)
    manufacturer: str | None = Field(None, max_length=255)
    android_version: str | None = Field(None, max_length=50)
    ios_version: str | None = Field(None, max_length=50)
    sdk_version: str | None = Field(None, max_length=50)
    imei: str | None = Field(None, max_length=50)
    imei2: str | None = Field(None, max_length=50)
    serial_number: str | None = Field(None, max_length=255)
    battery_level: int | None = Field(None, ge=0, le=100)
    battery_health: str | None = Field(None, max_length=50)
    storage_total: int | None = Field(None, ge=0)
    storage_free: int | None = Field(None, ge=0)
    is_rooted: bool = False
    is_encrypted: bool = False


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    model: str | None = Field(None, max_length=255)
    manufacturer: str | None = Field(None, max_length=255)
    android_version: str | None = Field(None, max_length=50)
    ios_version: str | None = Field(None, max_length=50)
    sdk_version: str | None = Field(None, max_length=50)
    imei: str | None = Field(None, max_length=50)
    imei2: str | None = Field(None, max_length=50)
    serial_number: str | None = Field(None, max_length=255)
    battery_level: int | None = Field(None, ge=0, le=100)
    battery_health: str | None = Field(None, max_length=50)
    storage_total: int | None = Field(None, ge=0)
    storage_free: int | None = Field(None, ge=0)
    is_rooted: bool | None = None
    is_encrypted: bool | None = None
    status: DeviceStatus | None = None


class DeviceResponse(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: DeviceStatus
    last_seen: datetime
    created_at: datetime
    updated_at: datetime


class DeviceListResponse(BaseModel):
    devices: list[DeviceResponse]
    total: int
    page: int
    page_size: int


# Diagnostic schemas
class DiagnosticBase(BaseModel):
    type: DiagnosticType


class DiagnosticCreate(DiagnosticBase):
    device_id: uuid.UUID


class DiagnosticUpdate(BaseModel):
    status: DiagnosticStatus | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: int | None = None


class DiagnosticResponse(DiagnosticBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    status: DiagnosticStatus
    result: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class DiagnosticListResponse(BaseModel):
    diagnostics: list[DiagnosticResponse]
    total: int
    page: int
    page_size: int


# Request/Response for running diagnostics
class RunDiagnosticRequest(BaseModel):
    device_serial: str = Field(..., min_length=1)
    type: DiagnosticType = DiagnosticType.FULL


class RunDiagnosticResponse(BaseModel):
    diagnostic_id: uuid.UUID
    device_serial: str
    type: DiagnosticType
    status: DiagnosticStatus
    message: str


# IMEI Check
class IMEICheckRequest(BaseModel):
    imei: str = Field(..., min_length=14, max_length=16, pattern=r"^\d{14,16}$")


class IMEICheckResponse(BaseModel):
    imei: str
    is_valid: bool
    is_blacklisted: bool | None = None
    carrier: str | None = None
    model: str | None = None
    checked_at: datetime
