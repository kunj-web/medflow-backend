from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    __table_args__ = (
        sa.Index("ix_audit_logs_action", "action"),
        sa.Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        sa.Index("ix_audit_logs_target", "target_type", "target_id"),
    )

    actor_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email = Column(String(255), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=False)
    target_id = Column(Uuid(as_uuid=True), nullable=True)
    summary = Column(Text, nullable=False)
    details = Column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
