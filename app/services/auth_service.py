from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from app.models.user import User
from app.models.patient import Patient
from app.models.hospital import Hospital
from app.core.security import hash_password, verify_password, create_token_pair, decode_token
from app.schemas.auth import RegisterRequest, LoginRequest


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, data: RegisterRequest) -> dict:
        # Check hospital exists
        hospital = self.db.query(Hospital).filter(
            Hospital.id == data.hospital_id,
            Hospital.is_active == True,
        ).first()
        if not hospital:
            raise ValueError("Hospital not found")

        # Check email not taken in this hospital
        existing = self.db.query(User).filter(
            User.email == data.email,
            User.hospital_id == data.hospital_id,
            User.deleted_at.is_(None),
        ).first()
        if existing:
            raise ValueError("Email already registered in this hospital")

        # Create user
        user = User(
            email=data.email,
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=data.role,
            hospital_id=data.hospital_id,
        )
        self.db.add(user)
        self.db.flush()

        # Auto-create patient profile if role is patient
        if data.role.value == "patient":
            patient = Patient(
                user_id=user.id,
                hospital_id=data.hospital_id,
                name=data.name,
            )
            self.db.add(patient)
            self.db.flush()

        self.db.commit()

        return create_token_pair(
            user_id=str(user.id),
            role=user.role.value,
            hospital_id=str(user.hospital_id),
        )

    def login(self, data: LoginRequest) -> dict:
        user = self.db.query(User).filter(
            User.email == data.email,
            User.hospital_id == data.hospital_id,
            User.deleted_at.is_(None),
        ).first()

        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        return create_token_pair(
            user_id=str(user.id),
            role=user.role.value,
            hospital_id=str(user.hospital_id),
        )

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        return create_token_pair(
            user_id=payload["sub"],
            role=payload["role"],
            hospital_id=payload["hospital_id"],
        )