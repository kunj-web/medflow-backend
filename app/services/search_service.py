from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AccountStatus, UserRole
from app.models.invoice import Invoice
from app.models.patient import Patient
from app.models.user import User
from app.schemas.search import SearchResponse, SearchResult


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, query: str, actor_user_id: UUID, actor_role: str) -> SearchResponse:
        q = query.strip()
        if len(q) < 2:
            return SearchResponse(data=[])

        like = f"%{q}%"
        results: list[SearchResult] = []

        results.extend(self._appointments(like, actor_user_id, actor_role))

        if actor_role == UserRole.WEBSITE_ADMIN.value:
            results.extend(self._patients(like))
            results.extend(self._doctors(like))
            results.extend(self._invoices(like, actor_user_id, actor_role))
        elif actor_role == UserRole.DOCTOR.value:
            results.extend(self._doctor_patients(like, actor_user_id))
        elif actor_role == UserRole.PATIENT.value:
            results.extend(self._invoices(like, actor_user_id, actor_role))

        return SearchResponse(data=results[:10])

    def _appointments(
        self, like: str, actor_user_id: UUID, actor_role: str
    ) -> list[SearchResult]:
        query = (
            self.db.query(Appointment, Patient, Doctor)
            .join(Patient, Appointment.patient_id == Patient.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
                Doctor.deleted_at.is_(None),
            )
        )

        if actor_role == UserRole.PATIENT.value:
            query = query.filter(Patient.user_id == actor_user_id)
        elif actor_role == UserRole.DOCTOR.value:
            query = query.filter(Doctor.user_id == actor_user_id)
        elif actor_role != UserRole.WEBSITE_ADMIN.value:
            return []

        query = query.filter(
            or_(
                cast(Appointment.token_number, String).ilike(like),
                cast(Appointment.slot_time, String).ilike(like),
                cast(Appointment.status, String).ilike(like),
                cast(Appointment.type, String).ilike(like),
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.phone.ilike(like),
                Doctor.first_name.ilike(like),
                Doctor.last_name.ilike(like),
                Doctor.specialization.ilike(like),
            )
        )

        rows = query.order_by(Appointment.slot_time.desc()).limit(5).all()
        return [
            self._appointment_result(appointment, patient, doctor)
            for appointment, patient, doctor in rows
        ]

    def _patients(self, like: str) -> list[SearchResult]:
        patients = (
            self.db.query(Patient)
            .filter(
                Patient.deleted_at.is_(None),
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.phone.ilike(like),
                    Patient.email.ilike(like),
                    Patient.city.ilike(like),
                    Patient.state.ilike(like),
                ),
            )
            .order_by(Patient.created_at.desc())
            .limit(5)
            .all()
        )
        return [self._patient_result(patient) for patient in patients]

    def _doctor_patients(self, like: str, doctor_user_id: UUID) -> list[SearchResult]:
        rows = (
            self.db.query(Patient, Appointment)
            .join(Appointment, Appointment.patient_id == Patient.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(
                Doctor.user_id == doctor_user_id,
                Patient.deleted_at.is_(None),
                Appointment.deleted_at.is_(None),
                Doctor.deleted_at.is_(None),
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.phone.ilike(like),
                    Patient.email.ilike(like),
                ),
            )
            .order_by(Appointment.slot_time.desc())
            .limit(10)
            .all()
        )

        seen: set[UUID] = set()
        results: list[SearchResult] = []
        for patient, appointment in rows:
            if patient.id in seen:
                continue
            seen.add(patient.id)
            results.append(
                SearchResult(
                    id=patient.id,
                    kind="patient",
                    title=self._person_name(patient.first_name, patient.last_name) or "Patient",
                    subtitle=patient.phone or patient.email or "Patient from your appointments",
                    meta=f"Appointment {self._format_datetime(appointment.slot_time)}",
                    href=f"/appointments#{appointment.id}",
                )
            )
        return results

    def _doctors(self, like: str) -> list[SearchResult]:
        doctors = (
            self.db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(
                Doctor.deleted_at.is_(None),
                User.deleted_at.is_(None),
                User.status == AccountStatus.ACTIVE,
                or_(
                    Doctor.first_name.ilike(like),
                    Doctor.last_name.ilike(like),
                    Doctor.specialization.ilike(like),
                    Doctor.phone.ilike(like),
                    Doctor.email.ilike(like),
                    Doctor.registration_number.ilike(like),
                ),
            )
            .order_by(Doctor.created_at.desc())
            .limit(5)
            .all()
        )
        return [self._doctor_result(doctor) for doctor in doctors]

    def _invoices(
        self, like: str, actor_user_id: UUID, actor_role: str
    ) -> list[SearchResult]:
        query = (
            self.db.query(Invoice)
            .join(Patient, Invoice.patient_id == Patient.id)
            .filter(Invoice.deleted_at.is_(None), Patient.deleted_at.is_(None))
        )

        if actor_role == UserRole.PATIENT.value:
            query = query.filter(Patient.user_id == actor_user_id)
        elif actor_role == UserRole.DOCTOR.value:
            query = (
                query.join(Appointment, Invoice.appointment_id == Appointment.id)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
                .filter(Doctor.user_id == actor_user_id, Doctor.deleted_at.is_(None))
            )
        elif actor_role != UserRole.WEBSITE_ADMIN.value:
            return []

        invoices = (
            query.filter(
                or_(
                    Invoice.invoice_number.ilike(like),
                    cast(Invoice.status, String).ilike(like),
                    cast(Invoice.total_amount, String).ilike(like),
                    cast(Invoice.balance_due, String).ilike(like),
                    Invoice.notes.ilike(like),
                )
            )
            .order_by(Invoice.created_at.desc())
            .limit(5)
            .all()
        )
        return [self._invoice_result(invoice) for invoice in invoices]

    def _appointment_result(
        self, appointment: Appointment, patient: Patient, doctor: Doctor
    ) -> SearchResult:
        patient_name = self._person_name(patient.first_name, patient.last_name) or "Patient"
        doctor_name = f"Dr. {self._person_name(doctor.first_name, doctor.last_name)}".strip()
        return SearchResult(
            id=appointment.id,
            kind="appointment",
            title=f"Token #{appointment.token_number or '-'}",
            subtitle=f"{patient_name} with {doctor_name}",
            meta=f"{appointment.status.value} - {self._format_datetime(appointment.slot_time)}",
            href=f"/appointments#{appointment.id}",
        )

    def _patient_result(self, patient: Patient) -> SearchResult:
        location = ", ".join(value for value in [patient.city, patient.state] if value)
        return SearchResult(
            id=patient.id,
            kind="patient",
            title=self._person_name(patient.first_name, patient.last_name) or "Patient",
            subtitle=patient.phone or patient.email or "Patient record",
            meta=location or "Profile",
            href=f"/patients#{patient.id}",
        )

    def _doctor_result(self, doctor: Doctor) -> SearchResult:
        return SearchResult(
            id=doctor.id,
            kind="doctor",
            title=f"Dr. {self._person_name(doctor.first_name, doctor.last_name)}".strip(),
            subtitle=doctor.specialization,
            meta=doctor.phone or doctor.email or "Doctor profile",
            href=f"/doctors#{doctor.id}",
        )

    def _invoice_result(self, invoice: Invoice) -> SearchResult:
        return SearchResult(
            id=invoice.id,
            kind="invoice",
            title=invoice.invoice_number,
            subtitle=f"{invoice.status.value} - Balance {self._format_money(invoice.balance_due)}",
            meta=f"Total {self._format_money(invoice.total_amount)}",
            href=f"/invoices#{invoice.id}",
        )

    @staticmethod
    def _person_name(first_name: str | None, last_name: str | None) -> str:
        return " ".join(value for value in [first_name, last_name] if value).strip()

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.strftime("%d %b %Y, %I:%M %p")

    @staticmethod
    def _format_money(value: Decimal | float | int) -> str:
        return f"INR {float(value):,.2f}"
