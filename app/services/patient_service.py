from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.appointment import AppointmentResponse
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.schemas.patient import (
    PatientResponse,
    PatientUpdate,
    PatientWithAppointmentsResponse,
)


class PatientRepository(BaseRepository[Patient]):
    def __init__(self, db: Session) -> None:
        super().__init__(Patient, db)

    def get_by_user_id(self, user_id: UUID) -> Patient | None:
        return (
            self.db.query(Patient)
            .filter(Patient.user_id == user_id, Patient.deleted_at.is_(None))
            .first()
        )

    def get_by_id_full(self, patient_id: UUID) -> Patient | None:
        return (
            self.db.query(Patient)
            .options(
                joinedload(Patient.appointments).joinedload(Appointment.doctor),
                joinedload(Patient.appointments).joinedload(Appointment.patient),
            )
            .filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
            .first()
        )

    def search(
        self, params: PaginationParams, query: str | None = None
    ) -> tuple[list[Patient], int]:
        q = self.db.query(Patient).filter(Patient.deleted_at.is_(None))
        if query:
            like = f"%{query}%"
            q = q.filter(
                Patient.first_name.ilike(like)
                | Patient.last_name.ilike(like)
                | Patient.phone.ilike(like)
            )
        total = q.count()
        patients = (
            q.order_by(Patient.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return patients, total


class PatientService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_repo = PatientRepository(db)

    def get_profile_for_user(self, user_id: UUID) -> Patient | None:
        return self.patient_repo.get_by_user_id(user_id)

    def get_by_id_with_appointments(
        self, patient_id: UUID
    ) -> PatientWithAppointmentsResponse:
        patient = self.patient_repo.get_by_id_full(patient_id)
        if not patient:
            raise LookupError("Patient not found")
        return PatientWithAppointmentsResponse.model_validate(patient)

    def list_all(
        self, params: PaginationParams, search: str | None = None
    ) -> PaginatedResponse[PatientResponse]:
        patients, total = self.patient_repo.search(params, search)
        return PaginatedResponse(
            data=[PatientResponse.model_validate(patient) for patient in patients],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    def update(self, patient_id: UUID, payload: PatientUpdate) -> PatientResponse:
        patient = self._get_or_404(patient_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "phone" in update_data or "email" in update_data:
            user = self.db.get(User, patient.user_id)
            if user:
                if "phone" in update_data:
                    user.phone = update_data["phone"]
                if "email" in update_data:
                    user.email = update_data["email"]

        for field, value in update_data.items():
            setattr(patient, field, value)
        self.db.commit()
        self.db.refresh(patient)
        return PatientResponse.model_validate(patient)

    def delete(self, patient_id: UUID) -> None:
        patient = self._get_or_404(patient_id)
        self.patient_repo.soft_delete(patient)
        self.db.commit()

    def doctor_has_access(self, patient_id: UUID, doctor_user_id: UUID) -> bool:
        return (
            self.db.query(Appointment.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.deleted_at.is_(None),
                Doctor.user_id == doctor_user_id,
                Doctor.deleted_at.is_(None),
            )
            .first()
            is not None
        )

    def get_appointment_history(
        self, patient_id: UUID, params: PaginationParams
    ) -> PaginatedResponse[AppointmentResponse]:
        self._get_or_404(patient_id)
        query = (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor),
            )
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.deleted_at.is_(None),
            )
        )
        total = query.count()
        appointments = (
            query.order_by(Appointment.slot_time.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return PaginatedResponse(
            data=[AppointmentResponse.model_validate(item) for item in appointments],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    def _get_or_404(self, patient_id: UUID) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise LookupError("Patient not found")
        return patient
