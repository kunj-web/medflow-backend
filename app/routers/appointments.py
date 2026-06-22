from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_db,
    require_active_status,
    require_role,
)
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.patient import Patient
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


def _can_view(db: Session, appointment: Appointment, current_user: dict) -> bool:
    role = current_user["role"]
    user_id = UUID(current_user["user_id"])
    if role == UserRole.WEBSITE_ADMIN.value:
        return True
    if role == UserRole.PATIENT.value:
        return (
            db.query(Patient.id)
            .filter(
                Patient.id == appointment.patient_id,
                Patient.user_id == user_id,
                Patient.deleted_at.is_(None),
            )
            .first()
            is not None
        )
    if role == UserRole.DOCTOR.value:
        return (
            db.query(Doctor.id)
            .filter(
                Doctor.id == appointment.doctor_id,
                Doctor.user_id == user_id,
                Doctor.deleted_at.is_(None),
            )
            .first()
            is not None
        )
    return False


@router.post(
    "/",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_status)],
)
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(UserRole.PATIENT)),
):
    try:
        return AppointmentService(db).book(
            data=data, patient_user_id=UUID(current_user["user_id"])
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=PaginatedResponse[AppointmentResponse])
def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
):
    repo = AppointmentRepository(db)
    user_id = UUID(current_user["user_id"])
    if current_user["role"] == UserRole.PATIENT.value:
        result = repo.get_paginated_for_patient_user(user_id, page, page_size)
    elif current_user["role"] == UserRole.DOCTOR.value:
        result = repo.get_paginated_for_doctor_user(user_id, page, page_size)
    else:
        result = repo.get_paginated_all(page, page_size)
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
    current_user: dict = Depends(
        require_role(UserRole.DOCTOR, UserRole.WEBSITE_ADMIN)
    ),
):
    repo = AppointmentRepository(db)
    if current_user["role"] == UserRole.WEBSITE_ADMIN.value:
        appointments = repo.get_all_for_date(date.today())
    else:
        doctor = (
            db.query(Doctor)
            .filter(
                Doctor.user_id == UUID(current_user["user_id"]),
                Doctor.deleted_at.is_(None),
            )
            .first()
        )
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")
        appointments = repo.get_doctor_appointments_for_date(doctor.id, date.today())
    return {"data": appointments, "total": len(appointments)}


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(
            UserRole.PATIENT, UserRole.DOCTOR, UserRole.WEBSITE_ADMIN
        )
    ),
):
    appointment = AppointmentRepository(db).get_by_id_with_relations(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_view(db, appointment, current_user):
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_active_status)],
)
def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancel,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(UserRole.PATIENT, UserRole.WEBSITE_ADMIN)
    ),
):
    try:
        return AppointmentService(db).cancel(
            appointment_id,
            data.reason,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_active_status)],
)
def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentReschedule,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_role(UserRole.PATIENT, UserRole.WEBSITE_ADMIN)
    ),
):
    try:
        return AppointmentService(db).reschedule(
            appointment_id,
            data,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
