from __future__ import annotations

from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.models.enums import DayOfWeek, Gender
from app.schemas.validators.phone import validate_indian_phone
from app.schemas.validators.common import (
    validate_non_empty_string,
    validate_positive_amount,
    validate_hex_color,
)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    slot_duration_minutes: int = 15

    @model_validator(mode="after")
    def end_after_start(self) -> "ScheduleCreate":
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
    reason: Optional[str] = None

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_non_empty_string(v)
        return v


class LeaveResponse(BaseModel):
    id: UUID
    leave_date: date
    reason: Optional[str]

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
    email: Optional[EmailStr] = None

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
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[Gender] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    is_active: Optional[bool] = None

    @field_validator("first_name", "last_name", "specialization", "qualification")
    @classmethod
    def non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_non_empty_string(v)
        return v

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_indian_phone(v)
        return v

    @field_validator("consultation_fee")
    @classmethod
    def valid_fee(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return validate_positive_amount(v)
        return v

    @field_validator("experience_years")
    @classmethod
    def non_negative_exp(cls, v: Optional[int]) -> Optional[int]:
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
    email: Optional[str]
    specialization: str
    qualification: str
    registration_number: str
    experience_years: int
    consultation_fee: float
    is_active: bool
    schedules: list[ScheduleResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Slot (read-only, returned by GET /doctors/{id}/slots)
# ---------------------------------------------------------------------------

class SlotResponse(BaseModel):
    datetime: str          # ISO-8601, e.g. "2025-06-10T09:00:00"
    is_available: bool