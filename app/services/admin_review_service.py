from __future__ import annotations

from datetime import time
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.doctor import Doctor, DoctorSchedule
from app.models.enums import AccountStatus, DayOfWeek, UserRole, WorkType
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.admin_review import (
    AdminDoctorReviewResponse,
    ApprovalHospitalCreate,
    DoctorApproveRequest,
)
from app.services.audit_log_service import AuditLogService


class AdminReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_pending_doctors(self) -> list[AdminDoctorReviewResponse]:
        doctors = (
            self.db.query(Doctor)
            .options(joinedload(Doctor.user))
            .join(User, Doctor.user_id == User.id)
            .filter(
                User.role == UserRole.DOCTOR,
                User.status == AccountStatus.PENDING,
                User.deleted_at.is_(None),
                Doctor.deleted_at.is_(None),
            )
            .order_by(Doctor.created_at.desc())
            .all()
        )
        return [self._to_response(doctor) for doctor in doctors]

    def approve_doctor(
        self,
        doctor_id: UUID,
        payload: DoctorApproveRequest,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> AdminDoctorReviewResponse:
        doctor = self._get_doctor_or_404(doctor_id)
        user = self._get_user_or_404(doctor.user_id)
        self._ensure_pending_doctor(user)

        if doctor.work_type == WorkType.HOSPITAL:
            self._approve_hospital_doctor(doctor, payload)
        elif payload.hospital_id is not None or payload.create_hospital is not None:
            raise ValueError("Clinic-based doctors cannot be linked to a hospital")

        user.status = AccountStatus.ACTIVE
        user.is_verified = True
        doctor.is_active = True
        self._ensure_default_schedules(doctor)
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="doctor.approved",
            target_type="doctor",
            target_id=doctor.id,
            summary=f"Approved Dr. {doctor.first_name} {doctor.last_name}",
            details={
                "doctor_email": user.email,
                "hospital_id": str(doctor.hospital_id) if doctor.hospital_id else None,
                "work_type": doctor.work_type.value,
            },
        )

        self.db.commit()
        self.db.refresh(doctor)
        return self._to_response(self._get_doctor_or_404(doctor.id))

    def reject_doctor(self, doctor_id: UUID) -> AdminDoctorReviewResponse:
        doctor = self._get_doctor_or_404(doctor_id)
        user = self._get_user_or_404(doctor.user_id)
        self._ensure_pending_doctor(user)

        user.status = AccountStatus.REJECTED
        doctor.is_active = False

        self.db.commit()
        self.db.refresh(doctor)
        return self._to_response(self._get_doctor_or_404(doctor.id))

    def _approve_hospital_doctor(
        self, doctor: Doctor, payload: DoctorApproveRequest
    ) -> None:
        if doctor.hospital_id is not None:
            if payload.hospital_id is not None and payload.hospital_id != doctor.hospital_id:
                raise ValueError("Doctor is already linked to a different hospital")
            if payload.create_hospital is not None:
                raise ValueError("Doctor is already linked to an existing hospital")
            hospital = self._get_active_hospital_or_404(doctor.hospital_id)
        elif payload.hospital_id is not None:
            hospital = self._get_active_hospital_or_404(payload.hospital_id)
        elif payload.create_hospital is not None:
            hospital = self._create_hospital(payload.create_hospital)
        else:
            raise ValueError("Hospital-based doctors must be linked before approval")

        doctor.hospital_id = hospital.id
        doctor.pending_hospital_name = None
        doctor.pending_hospital_city = None
        doctor.pending_hospital_state = None

    def _create_hospital(self, payload: ApprovalHospitalCreate) -> Hospital:
        hospital = Hospital(
            name=payload.name,
            city=payload.city,
            state=payload.state,
            address=payload.address,
            phone=payload.phone,
            email=str(payload.email) if payload.email is not None else None,
            is_active=True,
        )
        self.db.add(hospital)
        self.db.flush()
        return hospital

    def _ensure_default_schedules(self, doctor: Doctor) -> None:
        existing_count = (
            self.db.query(DoctorSchedule.id)
            .filter(
                DoctorSchedule.doctor_id == doctor.id,
                DoctorSchedule.deleted_at.is_(None),
            )
            .count()
        )
        if existing_count > 0:
            return

        for day in DayOfWeek:
            self.db.add(
                DoctorSchedule(
                    doctor_id=doctor.id,
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    slot_duration_minutes=10,
                    is_active=True,
                )
            )

    def _get_doctor_or_404(self, doctor_id: UUID) -> Doctor:
        doctor = (
            self.db.query(Doctor)
            .options(joinedload(Doctor.user))
            .filter(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
            .first()
        )
        if not doctor:
            raise LookupError("Doctor not found")
        return doctor

    def _get_user_or_404(self, user_id: UUID) -> User:
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None))
            .first()
        )
        if not user:
            raise LookupError("Doctor user not found")
        return user

    def _get_active_hospital_or_404(self, hospital_id: UUID) -> Hospital:
        hospital = (
            self.db.query(Hospital)
            .filter(
                Hospital.id == hospital_id,
                Hospital.is_active.is_(True),
                Hospital.deleted_at.is_(None),
            )
            .first()
        )
        if not hospital:
            raise LookupError("Hospital not found or inactive")
        return hospital

    @staticmethod
    def _ensure_pending_doctor(user: User) -> None:
        if user.role != UserRole.DOCTOR:
            raise ValueError("Only doctor accounts can be reviewed")
        if user.status != AccountStatus.PENDING:
            raise ValueError("Doctor is not pending review")

    @staticmethod
    def _to_response(doctor: Doctor) -> AdminDoctorReviewResponse:
        return AdminDoctorReviewResponse(
            id=doctor.id,
            user_id=doctor.user_id,
            status=doctor.user.status,
            first_name=doctor.first_name,
            last_name=doctor.last_name,
            gender=doctor.gender,
            phone=doctor.phone,
            email=doctor.email,
            specialization=doctor.specialization,
            qualification=doctor.qualification,
            registration_number=doctor.registration_number,
            experience_years=doctor.experience_years,
            consultation_fee=float(doctor.consultation_fee),
            is_active=doctor.is_active,
            work_type=doctor.work_type,
            hospital_id=doctor.hospital_id,
            clinic_name=doctor.clinic_name,
            clinic_city=doctor.clinic_city,
            clinic_address=doctor.clinic_address,
            pending_hospital_name=doctor.pending_hospital_name,
            pending_hospital_city=doctor.pending_hospital_city,
            pending_hospital_state=doctor.pending_hospital_state,
            created_at=doctor.created_at,
        )
