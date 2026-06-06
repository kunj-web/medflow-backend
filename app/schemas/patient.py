from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import BloodGroup, Gender
from app.schemas.appointment import AppointmentResponse
from app.schemas.validators.common import validate_non_empty_string
from app.schemas.validators.password import validate_password_strength
from app.schemas.validators.phone import validate_indian_phone

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
    email: EmailStr | None = None

    # Medical
    blood_group: BloodGroup | None = None
    allergies: str | None = None
    existing_conditions: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

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
    def valid_emergency_phone(cls, v: str | None) -> str | None:
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
    first_name: str | None = None
    last_name: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    email: EmailStr | None = None
    blood_group: BloodGroup | None = None
    allergies: str | None = None
    existing_conditions: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
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

    @field_validator("emergency_contact_phone")
    @classmethod
    def valid_emergency_phone(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_indian_phone(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def not_future(cls, v: date | None) -> date | None:
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
    email: str | None
    blood_group: BloodGroup | None
    allergies: str | None
    existing_conditions: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None

    model_config = {"from_attributes": True}


class PatientWithAppointmentsResponse(PatientResponse):
    appointments: list[AppointmentResponse] = []
