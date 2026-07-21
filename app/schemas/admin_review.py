from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.models.enums import AccountStatus, Gender, WorkType
from app.schemas.doctor import ScheduleResponse
from app.schemas.validators.common import validate_non_empty_string
from app.schemas.validators.phone import validate_indian_phone


class ApprovalHospitalCreate(BaseModel):
    name: str
    city: str | None = None
    state: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None

    @field_validator("name", "city", "state", "address")
    @classmethod
    def non_empty(cls, value: str | None) -> str | None:
        if value is not None:
            return validate_non_empty_string(value)
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        if value is not None:
            return validate_indian_phone(value)
        return value


class DoctorApproveRequest(BaseModel):
    hospital_id: UUID | None = None
    create_hospital: ApprovalHospitalCreate | None = None

    @model_validator(mode="after")
    def choose_one_hospital_source(self) -> DoctorApproveRequest:
        if self.hospital_id is not None and self.create_hospital is not None:
            raise ValueError("Provide either hospital_id or create_hospital, not both")
        return self


class DoctorRejectRequest(BaseModel):
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def non_empty_reason(cls, value: str | None) -> str | None:
        if value is not None:
            return validate_non_empty_string(value)
        return value


class AdminDoctorReviewResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: AccountStatus
    first_name: str
    last_name: str
    gender: Gender
    phone: str | None
    email: str | None
    specialization: str
    qualification: str | None
    registration_number: str | None
    experience_years: int
    consultation_fee: float
    is_active: bool
    work_type: WorkType
    hospital_id: UUID | None
    clinic_name: str | None
    clinic_city: str | None
    clinic_address: str | None
    pending_hospital_name: str | None
    pending_hospital_city: str | None
    pending_hospital_state: str | None
    schedules: list[ScheduleResponse] = []
    created_at: datetime
