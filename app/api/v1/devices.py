
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import get_db
from app.models.device import (
    Device,
    DevicePlatform,
    DeviceStatus,
)
from app.schemas.device import (
    DeviceCreate,
    DeviceListResponse,
    DeviceResponse,
    DeviceUpdate,
)
from app.services.adb_service import adb_service
from app.services.ios_service import ios_service

settings = get_settings()

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: DevicePlatform | None = None,
    status: DeviceStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Device)
    count_query = select(func.count(Device.id))

    if platform:
        query = query.where(Device.platform == platform)
        count_query = count_query.where(Device.platform == platform)
    if status:
        query = query.where(Device.status == status)
        count_query = count_query.where(Device.status == status)

    query = query.order_by(Device.last_seen.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    devices = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return DeviceListResponse(devices=devices, total=total, page=page, page_size=page_size)


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(device: DeviceCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Device).where(Device.serial == device.serial))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Device with this serial already exists")

    db_device = Device(**device.model_dump())
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/serial/{serial}", response_model=DeviceResponse)
async def get_device_by_serial(serial: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where(Device.serial == serial))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: str, device_update: DeviceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    for field, value in device_update.model_dump(exclude_unset=True).items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()


@router.post("/scan/android", response_model=list[DeviceResponse])
async def scan_android_devices(db: AsyncSession = Depends(get_db)):
    adb_devices = await adb_service.list_devices()
    results = []
    for adb_dev in adb_devices:
        if adb_dev.status != "device":
            continue
        info = await adb_service.get_device_info(adb_dev.serial)
        existing = await db.execute(select(Device).where(Device.serial == adb_dev.serial))
        device = existing.scalar_one_or_none()
        if not device:
            device = Device(
                serial=adb_dev.serial,
                platform=DevicePlatform.ANDROID,
                model=info.get("model") or adb_dev.model,
                manufacturer=info.get("manufacturer") or adb_dev.manufacturer,
                android_version=info.get("android_version"),
                sdk_version=info.get("sdk_version"),
                serial_number=info.get("serial_number"),
                battery_level=info.get("battery", {}).get("level"),
                battery_health=info.get("battery", {}).get("health"),
                storage_total=info.get("storage", {}).get("total_bytes"),
                storage_free=info.get("storage", {}).get("free_bytes"),
                is_rooted=info.get("is_rooted", False),
                is_encrypted=info.get("is_encrypted", False),
                status=DeviceStatus.CONNECTED,
            )
            db.add(device)
        else:
            device.model = info.get("model") or adb_dev.model or device.model
            device.manufacturer = info.get("manufacturer") or adb_dev.manufacturer or device.manufacturer
            device.android_version = info.get("android_version") or device.android_version
            device.sdk_version = info.get("sdk_version") or device.sdk_version
            device.serial_number = info.get("serial_number") or device.serial_number
            device.battery_level = info.get("battery", {}).get("level") or device.battery_level
            device.battery_health = info.get("battery", {}).get("health") or device.battery_health
            device.storage_total = info.get("storage", {}).get("total_bytes") or device.storage_total
            device.storage_free = info.get("storage", {}).get("free_bytes") or device.storage_free
            device.is_rooted = info.get("is_rooted", device.is_rooted)
            device.is_encrypted = info.get("is_encrypted", device.is_encrypted)
            device.status = DeviceStatus.CONNECTED
        results.append(device)

    await db.commit()
    for device in results:
        await db.refresh(device)
    return results


@router.post("/scan/ios", response_model=list[DeviceResponse])
async def scan_ios_devices(db: AsyncSession = Depends(get_db)):
    ios_devices = await ios_service.list_devices()
    results = []
    for ios_dev in ios_devices:
        info = await ios_service.get_device_info(ios_dev.udid)
        existing = await db.execute(select(Device).where(Device.serial == ios_dev.udid))
        device = existing.scalar_one_or_none()
        if not device:
            device = Device(
                serial=ios_dev.udid,
                platform=DevicePlatform.IOS,
                model=info.get("ProductType"),
                manufacturer="Apple",
                ios_version=info.get("ProductVersion"),
                serial_number=info.get("SerialNumber"),
                imei=info.get("InternationalMobileEquipmentIdentity"),
                battery_level=info.get("BatteryCurrentCapacity"),
                battery_health=str(info.get("BatteryHealth")) if info.get("BatteryHealth") else None,
                storage_total=info.get("TotalDiskCapacity"),
                storage_free=info.get("AvailableDiskSpace"),
                status=DeviceStatus.CONNECTED,
            )
            db.add(device)
        else:
            device.model = info.get("ProductType") or device.model
            device.ios_version = info.get("ProductVersion") or device.ios_version
            device.serial_number = info.get("SerialNumber") or device.serial_number
            device.imei = info.get("InternationalMobileEquipmentIdentity") or device.imei
            device.battery_level = info.get("BatteryCurrentCapacity") or device.battery_level
            device.battery_health = str(info.get("BatteryHealth")) if info.get("BatteryHealth") else device.battery_health
            device.storage_total = info.get("TotalDiskCapacity") or device.storage_total
            device.storage_free = info.get("AvailableDiskSpace") or device.storage_free
            device.status = DeviceStatus.CONNECTED
        results.append(device)

    await db.commit()
    for device in results:
        await db.refresh(device)
    return results
