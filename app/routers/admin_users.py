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
    dependencies=[Depends(require_super_admin)],
)
def create_admin(data: AdminUserCreate, db: Session = Depends(get_db)):
    try:
        return AdminUserService(db).create_admin(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/deactivate",
    response_model=AdminUserResponse,
    dependencies=[Depends(require_super_admin)],
)
def deactivate_admin(admin_id: UUID, db: Session = Depends(get_db)):
    try:
        return AdminUserService(db).deactivate_admin(admin_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/reactivate",
    response_model=AdminUserResponse,
    dependencies=[Depends(require_super_admin)],
)
def reactivate_admin(admin_id: UUID, db: Session = Depends(get_db)):
    try:
        return AdminUserService(db).reactivate_admin(admin_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{admin_id}/reset-password",
    response_model=AdminUserResponse,
    dependencies=[Depends(require_super_admin)],
)
def reset_admin_password(
    admin_id: UUID,
    data: AdminPasswordReset,
    db: Session = Depends(get_db),
):
    try:
        return AdminUserService(db).reset_admin_password(admin_id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
