"""
Centralized Pydantic schema exports.

This module provides clean access to all request/response schemas.

Example:
    from app.schemas import (
        PatientCreate,
        PatientResponse,
        AppointmentResponse,
    )
"""

# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentResponse,
    AppointmentUpdate,
    DoctorBrief,
    PatientBrief,
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

from app.schemas.doctor import (
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
    LeaveCreate,
    LeaveResponse,
    ScheduleCreate,
    ScheduleResponse,
    SlotResponse,
)

# ---------------------------------------------------------------------------
# Hospital
# ---------------------------------------------------------------------------

from app.schemas.hospital import (
    FeatureResponse,
    FeatureToggle,
    HospitalResponse,
    HospitalUpdate,
)

# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceLineItem,
    InvoiceResponse,
    PaymentRequest,
)

# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

from app.schemas.notification import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    NotificationResponse,
    UnreadCountResponse,
)

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

from app.schemas.pagination import (
    PaginatedResponse,
    PaginationParams,
)

# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

from app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    PatientWithAppointmentsResponse,
)

__all__ = [
    # Appointment
    "AppointmentCancel",
    "AppointmentCreate",
    "AppointmentReschedule",
    "AppointmentResponse",
    "AppointmentUpdate",
    "DoctorBrief",
    "PatientBrief",

    # Auth
    "ChangePasswordRequest",
    "LoginRequest",
    "MeResponse",
    "RefreshRequest",
    "RegisterRequest",
    "TokenResponse",

    # Doctor
    "DoctorCreate",
    "DoctorResponse",
    "DoctorUpdate",
    "LeaveCreate",
    "LeaveResponse",
    "ScheduleCreate",
    "ScheduleResponse",
    "SlotResponse",

    # Hospital
    "FeatureResponse",
    "FeatureToggle",
    "HospitalResponse",
    "HospitalUpdate",

    # Invoice
    "InvoiceCreate",
    "InvoiceLineItem",
    "InvoiceResponse",
    "PaymentRequest",

    # Notification
    "DeviceRegisterRequest",
    "DeviceRegisterResponse",
    "NotificationResponse",
    "UnreadCountResponse",

    # Pagination
    "PaginatedResponse",
    "PaginationParams",

    # Patient
    "PatientCreate",
    "PatientResponse",
    "PatientUpdate",
    "PatientWithAppointmentsResponse",
]