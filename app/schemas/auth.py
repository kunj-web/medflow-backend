from pydantic import BaseModel, EmailStr
from app.models.enums import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    phone: str
    password: str
    name: str
    role: UserRole = UserRole.PATIENT
    hospital_id: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    hospital_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str
    role: str
    hospital_id: str