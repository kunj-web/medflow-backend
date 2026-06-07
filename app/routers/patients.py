from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.appointment import AppointmentResponse
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    PatientWithAppointmentsResponse,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(db)

def _hospital_id(current_user: dict) -> UUID:
    return UUID(current_user["hospital_id"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient (admin / staff)",
)
def create_patient(
    payload: PatientCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: PatientService = Depends(get_service),
):
    try:
        return service.create(_hospital_id(current_user), payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=PaginatedResponse[PatientResponse],
    summary="List patients with optional search (admin / staff)",
)
def list_patients(
    search: str | None = Query(None, description="Search by name or phone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
    service: PatientService = Depends(get_service),
):
    params = PaginationParams(page=page, page_size=page_size)
    return service.list_all(_hospital_id(current_user), params, search)


@router.get(
    "/{patient_id}",
    response_model=PatientWithAppointmentsResponse,
    summary="Get a patient with their appointment history",
)
def get_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_service),
):
    """
    All roles can access — but patients can only access their own record.
    Admins, staff, and doctors can access any patient in the same hospital.
    """
    try:
        patient = service.get_by_id_with_appointments(
            _hospital_id(current_user), patient_id
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Patients can only see themselves
    if current_user.role == UserRole.PATIENT:
        if not hasattr(current_user, "patient") or current_user.patient.id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return patient


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient details (admin / staff, or the patient themselves)",
)
def update_patient(
    patient_id: UUID,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_service),
):
    # Patients may only update themselves
    if current_user.role == UserRole.PATIENT:
        if not hasattr(current_user, "patient") or current_user.patient.id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        return service.update(_hospital_id(current_user), patient_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a patient (admin only)",
)
def delete_patient(
    patient_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    service: PatientService = Depends(get_service),
):
    try:
        service.delete(_hospital_id(current_user), patient_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Appointment history
# ---------------------------------------------------------------------------

@router.get(
    "/{patient_id}/appointments",
    response_model=PaginatedResponse[AppointmentResponse],
    summary="Paginated appointment history for a patient",
)
def get_appointment_history(
    patient_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_service),
):
    # Patients can only see their own history
    if current_user.role == UserRole.PATIENT:
        if not hasattr(current_user, "patient") or current_user.patient.id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        params = PaginationParams(page=page, page_size=page_size)
        return service.get_appointment_history(
            _hospital_id(current_user), patient_id, params
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
