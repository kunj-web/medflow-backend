from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_email: str | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: UUID | None
    summary: str
    details: dict
    created_at: datetime

    model_config = {"from_attributes": True}
