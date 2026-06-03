from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.patient import Patient
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.appointment_repo import AppointmentRepository
from app.schemas.appointment import AppointmentResponse
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientWithAppointmentsResponse,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams


class PatientRepository(BaseRepository[Patient]):
    """Inline repo — patients don't yet need a dedicated file."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Patient)

    def get_by_phone(self, hospital_id: UUID, phone: str) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(
                Patient.hospital_id == hospital_id,
                Patient.phone == phone,
                Patient.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_id_full(self, patient_id: UUID) -> Optional[Patient]:
        from sqlalchemy.orm import joinedload
        return (
            self.db.query(Patient)
            .options(joinedload(Patient.appointments))
            .filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
            .first()
        )

    def search(
        self,
        hospital_id: UUID,
        params: PaginationParams,
        query: Optional[str] = None,
    ) -> tuple[list[Patient], int]:
        q = self.db.query(Patient).filter(
            Patient.hospital_id == hospital_id,
            Patient.deleted_at.is_(None),
        )
        if query:
            like = f"%{query}%"
            q = q.filter(
                Patient.first_name.ilike(like)
                | Patient.last_name.ilike(like)
                | Patient.phone.ilike(like)
            )
        total = q.count()
        items = (
            q.order_by(Patient.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return items, total


class PatientService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, hospital_id: UUID, payload: PatientCreate) -> PatientResponse:
        """Create a User (role=PATIENT) + Patient record in one transaction."""
        existing_user = (
            self.db.query(User)
            .filter(User.phone == payload.phone, User.deleted_at.is_(None))
            .first()
        )
        if existing_user:
            raise ValueError("A user with this phone number already exists")

        user = User(
            hospital_id=hospital_id,
            role=UserRole.PATIENT,
            phone=payload.phone,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.flush()

        patient = Patient(
            hospital_id=hospital_id,
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            phone=payload.phone,
            email=payload.email,
            blood_group=payload.blood_group,
            allergies=payload.allergies,
            existing_conditions=payload.existing_conditions,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone,
        )
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return PatientResponse.model_validate(patient)

    def get_by_id(self, hospital_id: UUID, patient_id: UUID) -> PatientResponse:
        patient = self._get_or_404(hospital_id, patient_id)
        return PatientResponse.model_validate(patient)

    def get_by_id_with_appointments(
        self, hospital_id: UUID, patient_id: UUID
    ) -> PatientWithAppointmentsResponse:
        patient = self.patient_repo.get_by_id_full(patient_id)
        if not patient or patient.hospital_id != hospital_id:
            raise LookupError("Patient not found")
        return PatientWithAppointmentsResponse.model_validate(patient)

    def list_all(
        self,
        hospital_id: UUID,
        params: PaginationParams,
        search: Optional[str] = None,
    ) -> PaginatedResponse[PatientResponse]:
        patients, total = self.patient_repo.search(hospital_id, params, search)
        items = [PatientResponse.model_validate(p) for p in patients]
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    def update(
        self, hospital_id: UUID, patient_id: UUID, payload: PatientUpdate
    ) -> PatientResponse:
        patient = self._get_or_404(hospital_id, patient_id)
        update_data = payload.model_dump(exclude_unset=True)

        # Keep User.phone / User.email in sync
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

    def delete(self, hospital_id: UUID, patient_id: UUID) -> None:
        patient = self._get_or_404(hospital_id, patient_id)
        self.patient_repo.soft_delete(patient)
        self.db.commit()

    # ------------------------------------------------------------------
    # Appointment history (convenience, wraps appointment_repo)
    # ------------------------------------------------------------------

    def get_appointment_history(
        self,
        hospital_id: UUID,
        patient_id: UUID,
        params: PaginationParams,
    ) -> PaginatedResponse[AppointmentResponse]:
        self._get_or_404(hospital_id, patient_id)
        appointments, total = self.appointment_repo.get_paginated_with_relations(
            hospital_id=hospital_id,
            params=params,
            patient_id=patient_id,
        )
        items = [AppointmentResponse.model_validate(a) for a in appointments]
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, hospital_id: UUID, patient_id: UUID) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient or patient.hospital_id != hospital_id:
            raise LookupError("Patient not found")
        return patient