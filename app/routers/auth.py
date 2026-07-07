from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, get_db
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.patient import Patient
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).register(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).login(data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).refresh(data.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUser, db: Session = Depends(get_db)):
    user_id = UUID(current_user["user_id"])
    user = db.query(User).filter(User.id == user_id).first()
    profile = None

    if current_user.get("role") == UserRole.PATIENT.value:
        profile = db.query(Patient).filter(Patient.user_id == user_id).first()
    elif current_user.get("role") == UserRole.DOCTOR.value:
        profile = db.query(Doctor).filter(Doctor.user_id == user_id).first()

    return {
        **current_user,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "first_name": profile.first_name if profile else None,
        "last_name": profile.last_name if profile else None,
    }
