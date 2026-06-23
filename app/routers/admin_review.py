from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import UserRole
from app.schemas.admin_review import (
    AdminDoctorReviewResponse,
    DoctorApproveRequest,
    DoctorRejectRequest,
)
from app.services.admin_review_service import AdminReviewService

router = APIRouter(prefix="/admin/doctors", tags=["admin doctor review"])


def get_service(db: Session = Depends(get_db)) -> AdminReviewService:
    return AdminReviewService(db)


@router.get(
    "/pending",
    response_model=list[AdminDoctorReviewResponse],
    dependencies=[
        Depends(require_active_status),
        Depends(require_role(UserRole.WEBSITE_ADMIN)),
    ],
)
def list_pending_doctors(
    service: AdminReviewService = Depends(get_service),
):
    return service.list_pending_doctors()


@router.post(
    "/{doctor_id}/approve",
    response_model=AdminDoctorReviewResponse,
    dependencies=[
        Depends(require_active_status),
        Depends(require_role(UserRole.WEBSITE_ADMIN)),
    ],
)
def approve_doctor(
    doctor_id: UUID,
    payload: DoctorApproveRequest,
    service: AdminReviewService = Depends(get_service),
):
    try:
        return service.approve_doctor(doctor_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/{doctor_id}/reject",
    response_model=AdminDoctorReviewResponse,
    dependencies=[
        Depends(require_active_status),
        Depends(require_role(UserRole.WEBSITE_ADMIN)),
    ],
)
def reject_doctor(
    doctor_id: UUID,
    payload: DoctorRejectRequest,
    service: AdminReviewService = Depends(get_service),
):
    try:
        return service.reject_doctor(doctor_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
