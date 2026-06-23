from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.doctor import Doctor
from app.models.enums import AccountStatus
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.pagination import PaginationParams
from app.schemas.public import (
    PublicDoctorResponse,
    PublicDoctorSearchResponse,
    PublicHospitalListResponse,
    PublicHospitalResponse,
)


class PublicService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_doctors(
        self,
        params: PaginationParams,
        city: str | None = None,
        specialization: str | None = None,
        hospital_id: UUID | None = None,
    ) -> PublicDoctorSearchResponse:
        query = (
            self.db.query(Doctor)
            .options(joinedload(Doctor.hospital))
            .join(User, Doctor.user_id == User.id)
            .outerjoin(Hospital, Doctor.hospital_id == Hospital.id)
            .filter(
                Doctor.is_active.is_(True),
                Doctor.deleted_at.is_(None),
                User.status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )

        if specialization:
            query = query.filter(Doctor.specialization.ilike(f"%{specialization}%"))
        if hospital_id:
            query = query.filter(Doctor.hospital_id == hospital_id)
        if city:
            like = f"%{city}%"
            query = query.filter(
                or_(
                    Doctor.clinic_city.ilike(like),
                    Hospital.city.ilike(like),
                )
            )

        total = query.count()
        doctors = (
            query.order_by(Doctor.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )

        return PublicDoctorSearchResponse(
            data=[self._doctor_to_response(doctor) for doctor in doctors],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    def list_hospitals(
        self,
        params: PaginationParams,
        city: str | None = None,
        search: str | None = None,
    ) -> PublicHospitalListResponse:
        query = self.db.query(Hospital).filter(
            Hospital.is_active.is_(True),
            Hospital.deleted_at.is_(None),
        )
        if city:
            query = query.filter(Hospital.city.ilike(f"%{city}%"))
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    Hospital.name.ilike(like),
                    Hospital.city.ilike(like),
                    Hospital.state.ilike(like),
                )
            )

        total = query.count()
        hospitals = (
            query.order_by(Hospital.name.asc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return PublicHospitalListResponse(
            data=[PublicHospitalResponse.model_validate(hospital) for hospital in hospitals],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    @staticmethod
    def _doctor_to_response(doctor: Doctor) -> PublicDoctorResponse:
        hospital = doctor.hospital
        return PublicDoctorResponse(
            id=doctor.id,
            first_name=doctor.first_name,
            last_name=doctor.last_name,
            gender=doctor.gender,
            specialization=doctor.specialization,
            qualification=doctor.qualification,
            experience_years=doctor.experience_years,
            consultation_fee=float(doctor.consultation_fee),
            work_type=doctor.work_type,
            hospital_id=doctor.hospital_id,
            hospital_name=hospital.name if hospital else None,
            city=doctor.clinic_city or (hospital.city if hospital else None),
            clinic_name=doctor.clinic_name,
        )
