from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.enums import AppointmentStatus, AppointmentType


# ─── Nested brief schemas (used inside responses) ─────────────────────────────

class DoctorBrief(BaseModel):
    id: UUID
    name: str
    specialization: str
    model_config = {"from_attributes": True}


class PatientBrief(BaseModel):
    id: UUID
    name: str
    model_config = {"from_attributes": True}


# ─── Request schemas ──────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    doctor_id: UUID
    slot_time: datetime
    type: AppointmentType = AppointmentType.CONSULTATION
    chief_complaint: Optional[str] = None


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    end_time: Optional[datetime] = None


class AppointmentReschedule(BaseModel):
    new_slot_time: datetime
    reason: Optional[str] = None


# ─── Response schemas ─────────────────────────────────────────────────────────

class AppointmentResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    slot_time: datetime
    end_time: Optional[datetime]
    status: AppointmentStatus
    type: AppointmentType
    chief_complaint: Optional[str]
    notes: Optional[str]
    token_number: Optional[int]
    doctor: DoctorBrief
    patient: PatientBrief
    created_at: datetime

    model_config = {"from_attributes": True}