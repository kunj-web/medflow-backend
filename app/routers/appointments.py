from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_role
from app.models.enums import UserRole
from app.repositories.appointment_repo import AppointmentRepository
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/", response_model=AppointmentResponse, status_code=201)
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.PATIENT)),
):
    """Patient books an appointment."""
    # Get patient profile id for current user
    from app.models.patient import Patient
    patient = db.query(Patient).filter(
        Patient.user_id == current_user["user_id"],
        Patient.deleted_at.is_(None),
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    try:
        return AppointmentService(db).book(
            data=data,
            hospital_id=UUID(current_user["hospital_id"]),
            patient_id=patient.id,
            user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/", response_model=PaginatedResponse[AppointmentResponse])
def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.STAFF)),
):
    """Admin/Staff view all hospital appointments."""
    repo = AppointmentRepository(db)
    result = repo.get_paginated_with_relations(
        hospital_id=UUID(current_user["hospital_id"]),
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=result.data,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/queue/today")
def today_queue(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.STAFF, UserRole.DOCTOR)),
):
    """Today's queue for staff dashboard."""
    repo = AppointmentRepository(db)
    appointments = repo.get_hospital_queue_for_date(
        hospital_id=UUID(current_user["hospital_id"]),
        date=date.today(),
    )
    return {"data": appointments, "total": len(appointments)}


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(
        UserRole.PATIENT, UserRole.DOCTOR, UserRole.STAFF, UserRole.ADMIN
    )),
):
    repo = AppointmentRepository(db)
    appointment = repo.get_by_id_with_relations(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancel,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(
        UserRole.PATIENT, UserRole.STAFF, UserRole.ADMIN
    )),
):
    try:
        return AppointmentService(db).cancel(
            appointment_id=appointment_id,
            hospital_id=UUID(current_user["hospital_id"]),
            reason=data.reason,
            cancelled_by_user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentReschedule,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(
        UserRole.PATIENT, UserRole.STAFF, UserRole.ADMIN
    )),
):
    try:
        return AppointmentService(db).reschedule(
            appointment_id=appointment_id,
            hospital_id=UUID(current_user["hospital_id"]),
            data=data,
            user_id=UUID(current_user["user_id"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
