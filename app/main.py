from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.admin_review import router as admin_review_router
from app.routers.appointments import router as appointments_router

# Routers — existing
from app.routers.auth import router as auth_router
from app.routers.config import router as config_router

# Routers — new
from app.routers.doctors import router as doctors_router
from app.routers.invoices import router as invoices_router
from app.routers.notifications import router as notifications_router
from app.routers.patients import router as patients_router
from app.routers.public import router as public_router

app = FastAPI(
    title="MedFlow API",
    version="1.0.0",
    description="AI-native hospital operations platform",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

PREFIX = "/api/v1"

app.include_router(auth_router,          prefix=PREFIX)
app.include_router(admin_review_router,  prefix=PREFIX)
app.include_router(appointments_router,  prefix=PREFIX)
app.include_router(config_router,        prefix=PREFIX)
app.include_router(notifications_router, prefix=PREFIX)
app.include_router(doctors_router,       prefix=PREFIX)
app.include_router(patients_router,      prefix=PREFIX)
app.include_router(invoices_router,      prefix=PREFIX)
app.include_router(public_router,        prefix=PREFIX)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
