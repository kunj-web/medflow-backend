# Import all models here so Alembic can detect them for migrations
from app.models.hospital import Hospital, HospitalFeature
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorSchedule, DoctorLeave
from app.models.appointment import Appointment
from app.models.invoice import Invoice
from app.models.notification import Notification, UserDevice

__all__ = [
    "Hospital",
    "HospitalFeature",
    "User",
    "Patient",
    "Doctor",
    "DoctorSchedule",
    "DoctorLeave",
    "Appointment",
    "Invoice",
    "Notification",
    "UserDevice",
]