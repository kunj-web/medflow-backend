from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import DayOfWeek, UserRole
from app.schemas.doctor import (
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


def get_service(db: Session = Depends(get_db)) -> DoctorService:
    return DoctorService(db)


def _actor(current_user: dict) -> tuple[UUID, bool]:
    return (
        UUID(current_user["user_id"]),
        current_user["role"] == UserRole.WEBSITE_ADMIN.value,
    )


@router.get("", response_model=PaginatedResponse[DoctorResponse])
def list_doctors(
    specialization: str | None = Query(None),
    hospital_id: UUID | None = Query(None),
    city: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: DoctorService = Depends(get_service),
):
    return service.list_public(
        PaginationParams(page=page, page_size=page_size),
        specialization,
        hospital_id,
        city,
    )


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: UUID, service: DoctorService = Depends(get_service)
):
    try:
        return service.get_public_by_id(doctor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/{doctor_id}",
    response_model=DoctorResponse,
    dependencies=[Depends(require_active_status)],
)
def update_doctor(
    doctor_id: UUID,
    payload: DoctorUpdate,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.update(doctor_id, payload, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete(
    "/{doctor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_active_status)],
)
def delete_doctor(
    doctor_id: UUID,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: DoctorService = Depends(get_service),
):
    try:
        service.delete(doctor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{doctor_id}/slots", response_model=list[SlotResponse])
def get_slots(
    doctor_id: UUID,
    date: date = Query(..., description="Target date (YYYY-MM-DD)"),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.get_slots(doctor_id, date)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{doctor_id}/schedule",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_status)],
)
def set_schedule(
    doctor_id: UUID,
    payload: ScheduleCreate,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.set_schedule(doctor_id, payload, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/{doctor_id}/schedules",
    response_model=list[ScheduleResponse],
    dependencies=[Depends(require_active_status)],
)
def list_schedules(
    doctor_id: UUID,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.list_schedules(doctor_id, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{doctor_id}/schedules",
    response_model=list[ScheduleResponse],
    dependencies=[Depends(require_active_status)],
)
def replace_weekly_schedule(
    doctor_id: UUID,
    payload: list[ScheduleCreate],
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.replace_weekly_schedule(
            doctor_id, payload, *_actor(current_user)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{doctor_id}/schedule/{day}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_active_status)],
)
def delete_schedule(
    doctor_id: UUID,
    day: DayOfWeek,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        service.delete_schedule(doctor_id, day, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{doctor_id}/leave",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_status)],
)
def add_leave(
    doctor_id: UUID,
    payload: LeaveCreate,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        return service.add_leave(doctor_id, payload, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{doctor_id}/leave/{leave_date}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_active_status)],
)
def cancel_leave(
    doctor_id: UUID,
    leave_date: date,
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
    service: DoctorService = Depends(get_service),
):
    try:
        service.cancel_leave(doctor_id, leave_date, *_actor(current_user))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
