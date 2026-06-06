from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import UserRole
from app.schemas.validators import (
    validate_indian_phone,
    validate_non_empty_string,
    validate_password_strength,
)

# ─── Request Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    phone: str
    password: str
    name: str
    role: UserRole = UserRole.PATIENT
    hospital_id: UUID

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v):
        return validate_indian_phone(v)

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v):
        return validate_password_strength(v)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        return validate_non_empty_string(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    hospital_id: UUID

    @field_validator("password")
    @classmethod
    def password_must_not_be_empty(cls, v):
        return validate_non_empty_string(v)


class RefreshRequest(BaseModel):
    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def token_must_not_be_empty(cls, v):
        return validate_non_empty_string(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, v):
        return validate_password_strength(v)


# ─── Response Schemas ─────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    role: str
    hospital_id: str
