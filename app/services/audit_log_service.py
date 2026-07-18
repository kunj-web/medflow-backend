from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.schemas.pagination import PaginatedResponse, PaginationParams


class AuditLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        actor_user_id: UUID | None,
        actor_role: str | None,
        action: str,
        target_type: str,
        summary: str,
        target_id: UUID | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        actor_email = None
        if actor_user_id is not None:
            actor = (
                self.db.query(User)
                .filter(User.id == actor_user_id, User.deleted_at.is_(None))
                .first()
            )
            actor_email = actor.email if actor else None

        log = AuditLog(
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            details=details or {},
        )
        self.db.add(log)
        return log

    def list_logs(
        self,
        params: PaginationParams,
        action: str | None = None,
        target_type: str | None = None,
    ) -> PaginatedResponse[AuditLogResponse]:
        query = self.db.query(AuditLog).filter(AuditLog.deleted_at.is_(None))

        if action:
            query = query.filter(AuditLog.action == action)
        if target_type:
            query = query.filter(AuditLog.target_type == target_type)

        total = query.count()
        logs = (
            query.order_by(AuditLog.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )

        return PaginatedResponse(
            data=[AuditLogResponse.model_validate(log) for log in logs],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )
