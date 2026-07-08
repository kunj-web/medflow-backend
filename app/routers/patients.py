from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import UserRole
from app.schemas.appointment import AppointmentResponse
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.patient import (
    PatientResponse,
    PatientUpdate,
    PatientWithAppointmentsResponse,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


def get_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(db)


def _authorize_patient_access(
    patient_id: UUID, current_user: dict, service: PatientService
) -> None:
    role = current_user["role"]
    user_id = UUID(current_user["user_id"])
    if role == UserRole.WEBSITE_ADMIN.value:
        return
    if role == UserRole.PATIENT.value:
        profile = service.get_profile_for_user(user_id)
        allowed = profile is not None and profile.id == patient_id
    elif role == UserRole.DOCTOR.value:
        allowed = service.doctor_has_access(patient_id, user_id)
    else:
        allowed = False
    if not allowed:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.get(
    "",
    response_model=PaginatedResponse[PatientResponse],
    dependencies=[Depends(require_active_status)],
)
def list_patients(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: PatientService = Depends(get_service),
):
    return service.list_all(
        PaginationParams(page=page, page_size=page_size), search
    )


@router.get(
    "/me",
    response_model=PatientResponse,
    dependencies=[Depends(require_active_status)],
)
def get_my_patient_profile(
    current_user: dict = Depends(require_role(UserRole.PATIENT)),
    service: PatientService = Depends(get_service),
):
    profile = service.get_profile_for_user(UUID(current_user["user_id"]))
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return PatientResponse.model_validate(profile)


@router.put(
    "/me",
    response_model=PatientResponse,
    dependencies=[Depends(require_active_status)],
)
def update_my_patient_profile(
    payload: PatientUpdate,
    current_user: dict = Depends(require_role(UserRole.PATIENT)),
    service: PatientService = Depends(get_service),
):
    profile = service.get_profile_for_user(UUID(current_user["user_id"]))
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return service.update(profile.id, payload)


@router.get(
    "/{patient_id}",
    response_model=PatientWithAppointmentsResponse,
    dependencies=[Depends(require_active_status)],
)
def get_patient(
    patient_id: UUID,
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
    service: PatientService = Depends(get_service),
):
    _authorize_patient_access(patient_id, current_user, service)
    try:
        return service.get_by_id_with_appointments(patient_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    dependencies=[Depends(require_active_status)],
)
def update_patient(
    patient_id: UUID,
    payload: PatientUpdate,
    current_user: dict = Depends(
        require_role(UserRole.PATIENT, UserRole.WEBSITE_ADMIN)
    ),
    service: PatientService = Depends(get_service),
):
    _authorize_patient_access(patient_id, current_user, service)
    try:
        return service.update(patient_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_active_status)],
)
def delete_patient(
    patient_id: UUID,
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    service: PatientService = Depends(get_service),
):
    try:
        service.delete(patient_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{patient_id}/appointments",
    response_model=PaginatedResponse[AppointmentResponse],
    dependencies=[Depends(require_active_status)],
)
def get_appointment_history(
    patient_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
    service: PatientService = Depends(get_service),
):
    _authorize_patient_access(patient_id, current_user, service)
    try:
        return service.get_appointment_history(
            patient_id, PaginationParams(page=page, page_size=page_size)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
