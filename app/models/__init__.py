"""
Centralized model exports.

This module imports all SQLAlchemy models so:
1. Alembic can detect them automatically
2. Relationships resolve correctly
3. Cleaner imports can be used across the app

Example:
    from app.models import User, Patient
"""

# Enums
# Appointment
from app.models.appointment import Appointment

# Doctor
from app.models.doctor import (
    Doctor,
    DoctorLeave,
    DoctorSchedule,
)
from app.models.enums import (
    AccountStatus,
    AppointmentStatus,
    AppointmentType,
    BloodGroup,
    DayOfWeek,
    Gender,
    InvoiceStatus,
    NotificationType,
    UserRole,
    WorkType,
)

# Hospital
from app.models.hospital import Hospital, HospitalFeature

# Invoice
from app.models.invoice import Invoice

# Notification
from app.models.notification import (
    Notification,
    UserDevice,
)

# Patient
from app.models.patient import Patient

# User
from app.models.user import User

__all__ = [
    # Enums
    "AccountStatus",
    "AppointmentStatus",
    "AppointmentType",
    "BloodGroup",
    "DayOfWeek",
    "Gender",
    "InvoiceStatus",
    "NotificationType",
    "UserRole",
    "WorkType",

    # Hospital
    "Hospital",
    "HospitalFeature",

    # User
    "User",

    # Patient
    "Patient",

    # Doctor
    "Doctor",
    "DoctorLeave",
    "DoctorSchedule",

    # Appointment
    "Appointment",

    # Invoice
    "Invoice",

    # Notification
    "Notification",
    "UserDevice",
]