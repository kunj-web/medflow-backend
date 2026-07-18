from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_active_status, require_role
from app.models.enums import UserRole
from app.schemas.audit_log import AuditLogResponse
from app.schemas.pagination import PaginatedResponse, PaginationParams
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/admin/audit-logs", tags=["audit logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogResponse],
    dependencies=[Depends(require_active_status)],
)
def list_audit_logs(
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(UserRole.WEBSITE_ADMIN)),
    db: Session = Depends(get_db),
):
    return AuditLogService(db).list_logs(
        PaginationParams(page=page, page_size=page_size),
        action=action,
        target_type=target_type,
    )
