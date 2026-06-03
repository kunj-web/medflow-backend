from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import BloodGroup, Gender
from app.schemas.validators.phone import validate_indian_phone
from app.schemas.validators.common import (
    validate_non_empty_string,
    validate_password_strength,
)
from app.schemas.appointment import AppointmentResponse


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

class PatientCreate(BaseModel):
    # Personal
    first_name: str
    last_name: str
    gender: Gender
    date_of_birth: date
    phone: str
    email: Optional[EmailStr] = None

    # Medical
    blood_group: Optional[BloodGroup] = None
    allergies: Optional[str] = None
    existing_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # Auth — linked User created alongside Patient
    password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return validate_non_empty_string(v)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: str) -> str:
        return validate_indian_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def valid_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_indian_phone(v)
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("date_of_birth")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    blood_group: Optional[BloodGroup] = None
    allergies: Optional[str] = None
    existing_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
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

    @field_validator("emergency_contact_phone")
    @classmethod
    def valid_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_indian_phone(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def not_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return v


class PatientResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    gender: Gender
    date_of_birth: date
    phone: str
    email: Optional[str]
    blood_group: Optional[BloodGroup]
    allergies: Optional[str]
    existing_conditions: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]

    model_config = {"from_attributes": True}


class PatientWithAppointmentsResponse(PatientResponse):
    appointments: list[AppointmentResponse] = []