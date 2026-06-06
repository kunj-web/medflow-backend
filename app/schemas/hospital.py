from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator

from app.schemas.validators.common import (
    validate_hex_color,
    validate_non_empty_string,
)
from app.schemas.validators.phone import validate_indian_phone

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
    name: str | None = None
    tagline: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    website: HttpUrl | None = None

    # Branding
    primary_color: str | None = None     # hex, e.g. "#1D9E75"
    secondary_color: str | None = None
    logo_url: str | None = None          # set by storage_service after R2 upload

    # Operational
    appointment_slot_duration_minutes: int | None = None
    max_advance_booking_days: int | None = None
    cancellation_cutoff_hours: int | None = None

    @field_validator("name", "address", "city", "state")
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

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def valid_color(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_hex_color(v)
        return v

    @field_validator("pincode")
    @classmethod
    def valid_pincode(cls, v: str | None) -> str | None:
        if v is not None and (not v.isdigit() or len(v) != 6):
            raise ValueError("pincode must be a 6-digit number")
        return v

    @field_validator("appointment_slot_duration_minutes")
    @classmethod
    def valid_slot_duration(cls, v: int | None) -> int | None:
        if v is not None and v not in (10, 15, 20, 30, 60):
            raise ValueError("appointment_slot_duration_minutes must be 10, 15, 20, 30, or 60")
        return v

    @field_validator("max_advance_booking_days", "cancellation_cutoff_hours")
    @classmethod
    def positive_int(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("must be a positive integer")
        return v


class HospitalResponse(BaseModel):
    id: UUID
    name: str
    tagline: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    website: str | None
    primary_color: str | None
    secondary_color: str | None
    logo_url: str | None
    appointment_slot_duration_minutes: int
    max_advance_booking_days: int
    cancellation_cutoff_hours: int
    features: list[FeatureResponse] = []

    model_config = {"from_attributes": True}
