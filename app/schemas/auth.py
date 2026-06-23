from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.models.enums import Gender, UserRole, WorkType
from app.schemas.validators import (
    validate_indian_phone,
    validate_non_empty_string,
    validate_password_strength,
)

# ─── Request Schemas ─────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    # --- Common fields (all roles) ---
    email: EmailStr
    phone: str
    password: str
    name: str
    role: UserRole = UserRole.PATIENT

    # --- Doctor-only fields (all optional here, enforced in validator) ---
    specialization: str | None = None
    qualification: str | None = None
    registration_number: str | None = None
    experience_years: int | None = None
    work_type: WorkType | None = None
    gender: Gender | None = None

    # Doctor + work_type=HOSPITAL, existing hospital selected from dropdown
    hospital_id: UUID | None = None

    # Doctor + work_type=HOSPITAL, hospital typed manually (not in dropdown)
    pending_hospital_name: str | None = None
    pending_hospital_city: str | None = None
    pending_hospital_state: str | None = None

    # Doctor + work_type=CLINIC
    clinic_name: str | None = None
    clinic_city: str | None = None
    clinic_address: str | None = None

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

    @field_validator("role")
    @classmethod
    def role_must_be_self_registerable(cls, v):
        """
        /register only ever creates PATIENT or DOCTOR accounts.
        WEBSITE_ADMIN is created exclusively via scripts/seed_admin.py
        or by an existing super admin through an internal panel.
        STAFF is not part of self-registration either (no flow defined
        for it yet).
        """
        if v not in (UserRole.PATIENT, UserRole.DOCTOR):
            raise ValueError(
                "Only 'patient' and 'doctor' can self-register. "
                "Other roles are created internally."
            )
        return v

    @staticmethod
    def _is_provided(value) -> bool:
        """
        Consistent 'was this field actually provided' check across the
        whole validator. None -> not provided. Empty/whitespace-only
        string -> not provided (a sloppy frontend sending "" should not
        count as real data). Non-string falsy values like 0 -> provided
        (0 is a legitimate value for e.g. experience_years).
        """
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        return True

    @model_validator(mode="after")
    def validate_doctor_fields(self):
        doctor_only_fields = {
            "specialization": self.specialization,
            "qualification": self.qualification,
            "registration_number": self.registration_number,
            "experience_years": self.experience_years,
            "work_type": self.work_type,
            "gender": self.gender,
            "hospital_id": self.hospital_id,
            "pending_hospital_name": self.pending_hospital_name,
            "pending_hospital_city": self.pending_hospital_city,
            "pending_hospital_state": self.pending_hospital_state,
            "clinic_name": self.clinic_name,
            "clinic_city": self.clinic_city,
            "clinic_address": self.clinic_address,
        }

        if self.role != UserRole.DOCTOR:
            # Patients (or any non-doctor role) must not submit any
            # doctor-only field. Silently ignoring these would hide
            # client bugs — reject explicitly instead.
            provided = [k for k, v in doctor_only_fields.items() if self._is_provided(v)]
            if provided:
                raise ValueError(
                    f"Fields not applicable to role '{self.role.value}': "
                    f"{', '.join(provided)}"
                )
            return self

        # Required doctor fields regardless of work_type
        if not self._is_provided(self.specialization):
            raise ValueError("specialization is required for doctor registration")
        if self.work_type is None:
            raise ValueError("work_type is required for doctor registration")
        if self.gender is None:
            raise ValueError("gender is required for doctor registration")

        if self.work_type == WorkType.HOSPITAL:
            has_existing = self.hospital_id is not None
            manual_fields_provided = [
                f for f in (
                    self.pending_hospital_name,
                    self.pending_hospital_city,
                    self.pending_hospital_state,
                )
                if self._is_provided(f)
            ]
            has_manual = len(manual_fields_provided) > 0

            if not has_existing and not has_manual:
                raise ValueError(
                    "Select a hospital from the dropdown or enter one manually"
                )
            if has_existing and has_manual:
                raise ValueError(
                    "Provide either hospital_id OR pending_hospital_* fields, "
                    "not both"
                )
            if has_manual and not self._is_provided(self.pending_hospital_name):
                raise ValueError(
                    "pending_hospital_name is required when entering a "
                    "hospital manually"
                )
            # Clinic fields must not be present for a hospital-based doctor
            if (
                self._is_provided(self.clinic_name)
                or self._is_provided(self.clinic_city)
                or self._is_provided(self.clinic_address)
            ):
                raise ValueError(
                    "clinic_* fields are not applicable when work_type is 'hospital'"
                )

        elif self.work_type == WorkType.CLINIC:
            if not self._is_provided(self.clinic_name) or not self._is_provided(self.clinic_city):
                raise ValueError(
                    "clinic_name and clinic_city are required for clinic-based doctors"
                )
            # Hospital fields must not be present for a clinic-based doctor
            if (
                self.hospital_id is not None
                or self._is_provided(self.pending_hospital_name)
                or self._is_provided(self.pending_hospital_city)
                or self._is_provided(self.pending_hospital_state)
            ):
                raise ValueError(
                    "hospital_id and pending_hospital_* fields are not applicable "
                    "when work_type is 'clinic'"
                )

        return self


class LoginRequest(BaseModel):
    """
    Login is just email + password now. Users are no longer hospital-scoped,
    so there is no hospital_id to disambiguate against — email is globally
    unique.
    """
    email: EmailStr
    password: str

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


# ─── Response Schemas ────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # Frontend needs these to redirect correctly post-login without an
    # extra /me call.
    role: str
    status: str
    is_super_admin: bool = False


class RegisterResponse(BaseModel):
    """
    Returned by /register instead of tokens. Registration never issues
    a token — patients still need to log in separately (matches the
    original "redirect to /login" flow), and doctors/pending accounts
    must not receive a usable token before approval.
    """
    user_id: str
    role: str
    status: str
    message: str


class MeResponse(BaseModel):
    user_id: str
    role: str
    status: str
    is_super_admin: bool = False
