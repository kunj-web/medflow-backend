from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from app.models.enums import AppointmentStatus, AppointmentType
from app.schemas.validators import (
    validate_slot_time,
    validate_non_empty_string,
    validate_cancellation_reason,
)


# ─── Nested Brief Schemas (embedded inside responses) ─────────────────────────

class DoctorBrief(BaseModel):
    id: UUID
    name: str
    specialization: str

    model_config = {"from_attributes": True}


class PatientBrief(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


# ─── Request Schemas ──────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    doctor_id: UUID
    slot_time: datetime
    type: AppointmentType = AppointmentType.CONSULTATION
    chief_complaint: Optional[str] = None

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
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    end_time: Optional[datetime] = None

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
    reason: Optional[str] = None

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
    hospital_id: UUID
    slot_time: datetime
    end_time: Optional[datetime]
    status: AppointmentStatus
    type: AppointmentType
    chief_complaint: Optional[str]
    notes: Optional[str]
    cancellation_reason: Optional[str]
    token_number: Optional[int]
    doctor: DoctorBrief
    patient: PatientBrief
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}