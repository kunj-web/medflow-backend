from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_super_admin
from app.schemas.admin_user import (
    AdminPasswordReset,
    AdminUserCreate,
    AdminUserResponse,
)
from app.services.admin_user_service import AdminUserService

router = APIRouter(prefix="/admin/users", tags=["admin users"])


@router.get(
    "",
    response_model=list[AdminUserResponse],
    dependencies=[Depends(require_super_admin)],
)
def list_admins(db: Session = Depends(get_db)):
    return AdminUserService(db).list_admins()


@router.post(
    "",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin(
    data: AdminUserCreate,
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return AdminUserService(db).create_admin(
            data,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/deactivate",
    response_model=AdminUserResponse,
)
def deactivate_admin(
    admin_id: UUID,
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return AdminUserService(db).deactivate_admin(
            admin_id,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/reactivate",
    response_model=AdminUserResponse,
)
def reactivate_admin(
    admin_id: UUID,
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return AdminUserService(db).reactivate_admin(
            admin_id,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/reset-password",
    response_model=AdminUserResponse,
)
def reset_admin_password(
    admin_id: UUID,
    data: AdminPasswordReset,
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return AdminUserService(db).reset_admin_password(
            admin_id,
            data,
            UUID(current_user["user_id"]),
            current_user["role"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
