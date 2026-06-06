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
from app.models.enums import (
    AppointmentStatus,
    AppointmentType,
    BloodGroup,
    DayOfWeek,
    Gender,
    InvoiceStatus,
    NotificationType,
    UserRole,
)

# Hospital
from app.models.hospital import Hospital, HospitalFeature

# User
from app.models.user import User

# Patient
from app.models.patient import Patient

# Doctor
from app.models.doctor import (
    Doctor,
    DoctorLeave,
    DoctorSchedule,
)

# Appointment
from app.models.appointment import Appointment

# Invoice
from app.models.invoice import Invoice

# Notification
from app.models.notification import (
    Notification,
    UserDevice,
)

__all__ = [
    # Enums
    "AppointmentStatus",
    "AppointmentType",
    "BloodGroup",
    "DayOfWeek",
    "Gender",
    "InvoiceStatus",
    "NotificationType",
    "UserRole",

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