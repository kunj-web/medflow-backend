from __future__ import annotations

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.models.enums import DayOfWeek, Gender, WorkType
from app.schemas.validators.common import (
    validate_non_empty_string,
    validate_positive_amount,
)
from app.schemas.validators.phone import validate_indian_phone

# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    slot_duration_minutes: int = 15

    @model_validator(mode="after")
    def end_after_start(self) -> ScheduleCreate:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

    @field_validator("slot_duration_minutes")
    @classmethod
    def valid_slot_duration(cls, v: int) -> int:
        if v not in (10, 15, 20, 30, 60):
            raise ValueError("slot_duration_minutes must be 10, 15, 20, 30, or 60")
        return v


class ScheduleResponse(BaseModel):
    id: UUID
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    slot_duration_minutes: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------

class LeaveCreate(BaseModel):
    leave_date: date
    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_non_empty_string(v)
        return v


class LeaveResponse(BaseModel):
    id: UUID
    leave_date: date
    reason: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

class DoctorCreate(BaseModel):
    # Personal
    first_name: str
    last_name: str
    gender: Gender
    phone: str
    email: EmailStr | None = None

    # Professional
    specialization: str
    qualification: str
    registration_number: str
    experience_years: int = 0

    # Financials
    consultation_fee: float

    # Auth — the linked User is created alongside the Doctor
    password: str

    @field_validator("first_name", "last_name", "specialization", "qualification", "registration_number")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return validate_non_empty_string(v)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        return validate_indian_phone(v)

    @field_validator("consultation_fee")
    @classmethod
    def valid_fee(cls, v: float) -> float:
        return validate_positive_amount(v)

    @field_validator("experience_years")
    @classmethod
    def non_negative_exp(cls, v: int) -> int:
        if v < 0:
            raise ValueError("experience_years cannot be negative")
        return v


class DoctorUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    gender: Gender | None = None
    phone: str | None = None
    email: EmailStr | None = None
    specialization: str | None = None
    qualification: str | None = None
    experience_years: int | None = None
    consultation_fee: float | None = None
    is_active: bool | None = None

    @field_validator("first_name", "last_name", "specialization", "qualification")
    @classmethod
    def non_empty(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_non_empty_string(v)
        return v

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_indian_phone(v)
        return v

    @field_validator("consultation_fee")
    @classmethod
    def valid_fee(cls, v: float | None) -> float | None:
        if v is not None:
            return validate_positive_amount(v)
        return v

    @field_validator("experience_years")
    @classmethod
    def non_negative_exp(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("experience_years cannot be negative")
        return v


class DoctorResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    gender: Gender
    phone: str
    email: str | None
    specialization: str
    qualification: str
    registration_number: str
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

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Slot (read-only, returned by GET /doctors/{id}/slots)
# ---------------------------------------------------------------------------

class SlotResponse(BaseModel):
    datetime: str          # ISO-8601, e.g. "2025-06-10T09:00:00"
    is_available: bool
