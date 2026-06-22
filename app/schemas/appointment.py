from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import AppointmentStatus, AppointmentType
from app.schemas.validators import (
    validate_cancellation_reason,
    validate_non_empty_string,
    validate_slot_time,
)

# ─── Nested Brief Schemas (embedded inside responses) ─────────────────────────

class DoctorBrief(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    specialization: str
    model_config = {"from_attributes": True}

class PatientBrief(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    model_config = {"from_attributes": True}

# ─── Request Schemas ──────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    doctor_id: UUID
    slot_time: datetime
    type: AppointmentType = AppointmentType.CONSULTATION
    chief_complaint: str | None = None

    @field_validator("slot_time")
    @classmethod
    def slot_time_must_be_valid(cls, v):
        return validate_slot_time(v)

    @field_validator("chief_complaint")
    @classmethod
    def chief_complaint_must_not_be_blank(cls, v):
        if v is not None:
            return validate_non_empty_string(v)
        return v


class AppointmentUpdate(BaseModel):
    status: AppointmentStatus | None = None
    notes: str | None = None
    end_time: datetime | None = None

    @field_validator("notes")
    @classmethod
    def notes_must_not_be_blank(cls, v):
        if v is not None:
            return validate_non_empty_string(v)
        return v


class AppointmentCancel(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_must_be_meaningful(cls, v):
        return validate_cancellation_reason(v)


class AppointmentReschedule(BaseModel):
    new_slot_time: datetime
    reason: str | None = None

    @field_validator("new_slot_time")
    @classmethod
    def new_slot_must_be_valid(cls, v):
        return validate_slot_time(v)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, v):
        if v is not None:
            return validate_non_empty_string(v)
        return v


# ─── Response Schema ──────────────────────────────────────────────────────────

class AppointmentResponse(BaseModel):
    id: UUID
    # Historical snapshot copied from the doctor at booking time. Clinic
    # doctors intentionally produce appointments without a hospital.
    hospital_id: UUID | None
    slot_time: datetime
    end_time: datetime | None
    status: AppointmentStatus
    type: AppointmentType
    chief_complaint: str | None
    notes: str | None
    cancellation_reason: str | None
    token_number: int | None
    doctor: DoctorBrief
    patient: PatientBrief
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
