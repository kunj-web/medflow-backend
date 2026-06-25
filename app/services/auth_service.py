from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_token_pair, decode_token, hash_password, verify_password
from app.models.doctor import Doctor
from app.models.enums import AccountStatus, UserRole, WorkType
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, data: RegisterRequest) -> dict:
        """
        Returns a registration status payload — NEVER tokens.
        Patients must still log in separately after registering.
        Doctors are PENDING and cannot log in until a website admin
        approves them. Issuing a token here would let a PENDING doctor
        bypass approval entirely.
        """
        # Email is globally unique now — no hospital_id to disambiguate
        existing = self.db.query(User).filter(
            User.email == data.email,
            User.deleted_at.is_(None),
        ).first()
        if existing:
            raise ValueError("Email already registered")

        # If doctor selected an existing hospital, verify it's real and
        # active before linking — don't trust a client-supplied UUID blind.
        if (
            data.role == UserRole.DOCTOR
            and data.work_type == WorkType.HOSPITAL
            and data.hospital_id is not None
        ):
            hospital = self.db.query(Hospital).filter(
                Hospital.id == data.hospital_id,
                Hospital.is_active == True,  # noqa: E712
                Hospital.deleted_at.is_(None),
            ).first()
            if not hospital:
                raise ValueError("Selected hospital not found or inactive")

        # Patients are ACTIVE immediately; doctors need approval
        initial_status = (
            AccountStatus.ACTIVE
            if data.role == UserRole.PATIENT
            else AccountStatus.PENDING
        )

        user = User(
            email=data.email,
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=data.role,
            status=initial_status,
        )
        self.db.add(user)

        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            # Catches the soft-delete edge case: the application-level
            # duplicate check above only excludes ACTIVE rows with this
            # email, but the DB-level unique index on users.email is
            # currently NOT partial (doesn't exclude soft-deleted rows)
            # — see migration TODO (Phase 4): index should become
            # UNIQUE(email) WHERE deleted_at IS NULL. Until then, a
            # soft-deleted user's email cannot actually be reused, even
            # though app logic implies it should be. The IntegrityError
            # fires HERE at flush (the INSERT), not at the later commit
            # — this try/except must wrap the flush, not the commit.
            raise ValueError(
                "Email already registered. If you previously had an "
                "account with this email, contact support."
            )

        if data.role == UserRole.PATIENT:
            name_parts = data.name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            patient = Patient(
                user_id=user.id,
                first_name=first_name,
                last_name=last_name,
                phone=data.phone,
                email=data.email,
            )
            self.db.add(patient)
            self.db.flush()

        elif data.role == UserRole.DOCTOR:
            name_parts = data.name.strip().split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            doctor_kwargs = {
                "user_id": user.id,
                "first_name": first_name,
                "last_name": last_name,
                "phone": data.phone,
                "email": data.email,
                "specialization": data.specialization,
                "qualification": data.qualification,
                "registration_number": data.registration_number,
                "experience_years": data.experience_years or 0,
                "work_type": data.work_type,
                "gender": data.gender,
            }

            if data.work_type == WorkType.HOSPITAL:
                if data.hospital_id is not None:
                    doctor_kwargs["hospital_id"] = data.hospital_id
                else:
                    doctor_kwargs["pending_hospital_name"] = data.pending_hospital_name
                    doctor_kwargs["pending_hospital_city"] = data.pending_hospital_city
                    doctor_kwargs["pending_hospital_state"] = data.pending_hospital_state

            elif data.work_type == WorkType.CLINIC:
                doctor_kwargs["clinic_name"] = data.clinic_name
                doctor_kwargs["clinic_city"] = data.clinic_city
                doctor_kwargs["clinic_address"] = data.clinic_address

            doctor = Doctor(**doctor_kwargs)
            self.db.add(doctor)
            self.db.flush()

        self.db.commit()

        message = (
            "Registration successful. You can now log in."
            if initial_status == AccountStatus.ACTIVE
            else "Registration submitted. Your account is pending approval "
                 "by a website admin. You will be able to log in once approved."
        )

        return {
            "user_id": str(user.id),
            "role": user.role.value,
            "status": user.status.value,
            "message": message,
        }

    def login(self, data: LoginRequest) -> dict:
        user = self.db.query(User).filter(
            User.email == data.email,
            User.deleted_at.is_(None),
        ).first()

        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if user.status == AccountStatus.PENDING:
            raise ValueError("Your account is pending approval")

        if user.status == AccountStatus.REJECTED:
            raise ValueError("Your registration was rejected")

        return create_token_pair(
            user_id=str(user.id),
            role=user.role.value,
            status=user.status.value,
            is_super_admin=user.is_super_admin,
        )

    def refresh(self, refresh_token: str) -> dict:
        """
        Re-checks current DB status on every refresh rather than trusting
        the stale claims in the refresh token. A user who was ACTIVE when
        they logged in but has since been deactivated/rejected must not
        be able to keep refreshing their way to new access tokens.

        Fails closed: if status is missing/unrecognized for any reason,
        the refresh is rejected rather than defaulted to ACTIVE.
        """
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        raw_user_id = payload.get("sub")
        if not raw_user_id:
            raise ValueError("Invalid refresh token")

        try:
            user_id = UUID(raw_user_id)
        except ValueError as exc:
            raise ValueError("Invalid refresh token") from exc

        user = self.db.query(User).filter(
            User.id == user_id,
            User.deleted_at.is_(None),
        ).first()

        if not user:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if user.status != AccountStatus.ACTIVE:
            raise ValueError("Account is not active")

        return create_token_pair(
            user_id=str(user.id),
            role=user.role.value,
            status=user.status.value,
            is_super_admin=user.is_super_admin,
        )
    
