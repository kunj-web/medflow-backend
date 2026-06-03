from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator

from app.schemas.validators.phone import validate_indian_phone
from app.schemas.validators.common import (
    validate_non_empty_string,
    validate_hex_color,
)


# ---------------------------------------------------------------------------
# Feature toggle (used inside HospitalResponse and FeatureToggle)
# ---------------------------------------------------------------------------

class FeatureToggle(BaseModel):
    feature_key: str
    is_enabled: bool

    @field_validator("feature_key")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return validate_non_empty_string(v)


class FeatureResponse(BaseModel):
    id: UUID
    feature_key: str
    is_enabled: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Hospital
# ---------------------------------------------------------------------------

class HospitalUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    website: Optional[HttpUrl] = None

    # Branding
    primary_color: Optional[str] = None     # hex, e.g. "#1D9E75"
    secondary_color: Optional[str] = None
    logo_url: Optional[str] = None          # set by storage_service after R2 upload

    # Operational
    appointment_slot_duration_minutes: Optional[int] = None
    max_advance_booking_days: Optional[int] = None
    cancellation_cutoff_hours: Optional[int] = None

    @field_validator("name", "address", "city", "state")
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

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def valid_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_hex_color(v)
        return v

    @field_validator("pincode")
    @classmethod
    def valid_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v.isdigit() or len(v) != 6):
            raise ValueError("pincode must be a 6-digit number")
        return v

    @field_validator("appointment_slot_duration_minutes")
    @classmethod
    def valid_slot_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (10, 15, 20, 30, 60):
            raise ValueError("appointment_slot_duration_minutes must be 10, 15, 20, 30, or 60")
        return v

    @field_validator("max_advance_booking_days", "cancellation_cutoff_hours")
    @classmethod
    def positive_int(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("must be a positive integer")
        return v


class HospitalResponse(BaseModel):
    id: UUID
    name: str
    tagline: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    website: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    logo_url: Optional[str]
    appointment_slot_duration_minutes: int
    max_advance_booking_days: int
    cancellation_cutoff_hours: int
    features: list[FeatureResponse] = []

    model_config = {"from_attributes": True}