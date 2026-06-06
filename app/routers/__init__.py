from app.routers.auth import router as auth_router
from app.routers.appointments import router as appointments_router
from app.routers.config import router as config_router
from app.routers.doctors import router as doctors_router
from app.routers.hospital_admin import router as hospital_admin_router
from app.routers.invoices import router as invoices_router
from app.routers.notifications import router as notifications_router
from app.routers.patients import router as patients_router

__all__ = [
    "auth_router",
    "appointments_router",
    "config_router",
    "doctors_router",
    "hospital_admin_router",
    "invoices_router",
    "notifications_router",
    "patients_router",
]