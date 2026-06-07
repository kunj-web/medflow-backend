from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.enums import DayOfWeek, UserRole
from app.models.user import User
from app.schemas.doctor import (
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
    LeaveCreate,
    LeaveResponse,
    ScheduleCreate,
    ScheduleResponse,
    SlotResponse,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["doctors"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_service(db: Session = Depends(get_db)) -> DoctorService:
    return DoctorService(db)


def _hospital_id(current_user: dict) -> UUID:
    return UUID(current_user["hospital_id"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a doctor (admin only)",
)
def create_doctor(
    payload: DoctorCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.create(_hospital_id(current_user), payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "",
    response_model=PaginatedResponse[DoctorResponse],
    summary="List doctors",
)
def list_doctors(
    specialization: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: DoctorService = Depends(get_service),
):
    params = PaginationParams(page=page, page_size=page_size)
    return service.list_all(_hospital_id(current_user), params, specialization)


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Get a doctor by ID",
)
def get_doctor(
    doctor_id: UUID,
    current_user: User = Depends(get_current_user),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.get_by_id(_hospital_id(current_user), doctor_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Update a doctor (admin only)",
)
def update_doctor(
    doctor_id: UUID,
    payload: DoctorUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.update(_hospital_id(current_user), doctor_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete(
    "/{doctor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a doctor (admin only)",
)
def delete_doctor(
    doctor_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        service.delete(_hospital_id(current_user), doctor_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

@router.get(
    "/{doctor_id}/slots",
    response_model=list[SlotResponse],
    summary="Get available slots for a doctor on a given date",
)
def get_slots(
    doctor_id: UUID,
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.get_slots(_hospital_id(current_user), doctor_id, date)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@router.post(
    "/{doctor_id}/schedule",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set (upsert) a schedule entry for a weekday (admin only)",
)
def set_schedule(
    doctor_id: UUID,
    payload: ScheduleCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.set_schedule(_hospital_id(current_user), doctor_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.delete(
    "/{doctor_id}/schedule/{day}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a schedule entry for a weekday (admin only)",
)
def delete_schedule(
    doctor_id: UUID,
    day: DayOfWeek,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        service.delete_schedule(_hospital_id(current_user), doctor_id, day)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------

@router.post(
    "/{doctor_id}/leave",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mark a leave date for a doctor (admin only)",
)
def add_leave(
    doctor_id: UUID,
    payload: LeaveCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.add_leave(_hospital_id(current_user), doctor_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete(
    "/{doctor_id}/leave/{leave_date}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a leave date for a doctor (admin only)",
)
def cancel_leave(
    doctor_id: UUID,
    leave_date: date,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        service.cancel_leave(_hospital_id(current_user), doctor_id, leave_date)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
