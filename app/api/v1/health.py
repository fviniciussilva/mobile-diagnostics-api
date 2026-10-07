from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import get_db

settings = get_settings()

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}


@router.get("/adb")
async def health_check_adb():
    from app.services.adb_service import adb_service
    try:
        devices = await adb_service.list_devices()
        return {"status": "ok", "adb": "available", "devices_count": len(devices)}
    except Exception as e:
        return {"status": "error", "adb": "unavailable", "error": str(e)}


@router.get("/ios")
async def health_check_ios():
    from app.services.ios_service import ios_service
    try:
        devices = await ios_service.list_devices()
        return {"status": "ok", "ios": "available", "devices_count": len(devices)}
    except Exception as e:
        return {"status": "error", "ios": "unavailable", "error": str(e)}
