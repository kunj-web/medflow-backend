from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.validators.password import validate_password_strength


class AdminUserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        return validate_password_strength(v)


class AdminPasswordReset(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        return validate_password_strength(v)


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    phone: str | None
    status: str
    is_active: bool
    is_verified: bool
    is_super_admin: bool
    created_at: datetime
