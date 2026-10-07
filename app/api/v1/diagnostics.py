import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import get_db
from app.models.device import (
    Device,
    DevicePlatform,
    Diagnostic,
    DiagnosticStatus,
    DiagnosticType,
)
from app.schemas.device import (
    DiagnosticListResponse,
    DiagnosticResponse,
    IMEICheckRequest,
    IMEICheckResponse,
    RunDiagnosticRequest,
    RunDiagnosticResponse,
)
from app.services.adb_service import adb_service
from app.services.ios_service import ios_service

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


async def run_diagnostic_background(
    diagnostic_id: uuid.UUID,
    device_serial: str,
    diag_type: DiagnosticType,
):
    from app.main import async_session_maker
    from app.models.device import Diagnostic as DiagnosticModel

    async with async_session_maker() as db:
        # Update status to running
        result = await db.execute(select(DiagnosticModel).where(DiagnosticModel.id == diagnostic_id))
        diagnostic = result.scalar_one_or_none()
        if not diagnostic:
            return

        diagnostic.status = DiagnosticStatus.RUNNING
        diagnostic.started_at = datetime.utcnow()
        await db.commit()

        try:
            # Run diagnostic based on platform
            device_result = await db.execute(select(Device).where(Device.serial == device_serial))
            device = device_result.scalar_one_or_none()

            if not device:
                diagnostic.status = DiagnosticStatus.FAILED
                diagnostic.error_message = "Device not found in database"
                diagnostic.completed_at = datetime.utcnow()
                await db.commit()
                return

            if device.platform == DevicePlatform.ANDROID:
                result_data = await adb_service.run_diagnostic(device_serial, diag_type.value)
            elif device.platform == DevicePlatform.IOS:
                result_data = await ios_service.run_diagnostic(device_serial, diag_type.value)
            else:
                result_data = {"error": "Unknown platform"}

            diagnostic.status = DiagnosticStatus.COMPLETED
            diagnostic.result = str(result_data)  # Store as JSON string
            diagnostic.completed_at = datetime.utcnow()
            if diagnostic.started_at:
                diagnostic.duration_ms = int((diagnostic.completed_at - diagnostic.started_at).total_seconds() * 1000)
        except Exception as e:
            diagnostic.status = DiagnosticStatus.FAILED
            diagnostic.error_message = str(e)
            diagnostic.completed_at = datetime.utcnow()
        finally:
            await db.commit()


@router.post("/run", response_model=RunDiagnosticResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_diagnostic(
    request: RunDiagnosticRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Verify device exists
    result = await db.execute(select(Device).where(Device.serial == request.device_serial))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found. Scan first.")

    # Create diagnostic record
    diagnostic = Diagnostic(
        device_id=device.id,
        type=request.type,
        status=DiagnosticStatus.PENDING,
    )
    db.add(diagnostic)
    await db.commit()
    await db.refresh(diagnostic)

    # Run in background
    background_tasks.add_task(run_diagnostic_background, diagnostic.id, request.device_serial, request.type)

    return RunDiagnosticResponse(
        diagnostic_id=diagnostic.id,
        device_serial=request.device_serial,
        type=request.type,
        status=DiagnosticStatus.PENDING,
        message="Diagnostic started. Check status via GET /diagnostics/{id}",
    )


@router.get("", response_model=DiagnosticListResponse)
async def list_diagnostics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: uuid.UUID | None = None,
    status: DiagnosticStatus | None = None,
    type: DiagnosticType | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Diagnostic)
    count_query = select(func.count(Diagnostic.id))

    if device_id:
        query = query.where(Diagnostic.device_id == device_id)
        count_query = count_query.where(Diagnostic.device_id == device_id)
    if status:
        query = query.where(Diagnostic.status == status)
        count_query = count_query.where(Diagnostic.status == status)
    if type:
        query = query.where(Diagnostic.type == type)
        count_query = count_query.where(Diagnostic.type == type)

    query = query.order_by(Diagnostic.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    diagnostics = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return DiagnosticListResponse(diagnostics=diagnostics, total=total, page=page, page_size=page_size)


@router.get("/{diagnostic_id}", response_model=DiagnosticResponse)
async def get_diagnostic(diagnostic_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Diagnostic).where(Diagnostic.id == diagnostic_id))
    diagnostic = result.scalar_one_or_none()
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    return diagnostic


@router.get("/device/{device_serial}", response_model=DiagnosticListResponse)
async def get_device_diagnostics(
    device_serial: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    device_result = await db.execute(select(Device).where(Device.serial == device_serial))
    device = device_result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    query = select(Diagnostic).where(Diagnostic.device_id == device.id).order_by(Diagnostic.created_at.desc())
    count_query = select(func.count(Diagnostic.id)).where(Diagnostic.device_id == device.id)

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    diagnostics = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return DiagnosticListResponse(diagnostics=diagnostics, total=total, page=page, page_size=page_size)


@router.post("/imei-check", response_model=IMEICheckResponse)
async def check_imei(request: IMEICheckRequest, db: AsyncSession = Depends(get_db)):
    # Basic Luhn algorithm validation for IMEI
    def luhn_check(imei: str) -> bool:
        digits = [int(d) for d in imei[:-1]]
        check_digit = int(imei[-1])
        total = 0
        # Double every second digit from the RIGHT (excluding check digit)
        for i in range(len(digits) - 1, -1, -1):
            d = digits[i]
            pos_from_right = len(digits) - 1 - i
            if pos_from_right % 2 == 0:  # Every second from right (0, 2, 4...)
                doubled = d * 2
                total += doubled if doubled < 10 else doubled - 9
            else:
                total += d
        return (total + check_digit) % 10 == 0

    is_valid = luhn_check(request.imei)

    # Check local database for blacklisted
    is_blacklisted = False
    carrier = None
    model = None

    if is_valid:
        # Could integrate with external IMEI check API here
        pass

    return IMEICheckResponse(
        imei=request.imei,
        is_valid=is_valid,
        is_blacklisted=is_blacklisted,
        carrier=carrier,
        model=model,
        checked_at=datetime.utcnow(),
    )
