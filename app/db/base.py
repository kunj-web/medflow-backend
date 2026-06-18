import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = datetime.now(UTC)


class HospitalScopedMixin:
    """
    Adds an optional hospital_id FK.

    NOTE: As of the marketplace model, hospital_id is nullable everywhere.
    It no longer represents a tenancy boundary — it represents an
    affiliation (Doctor) or a historical snapshot (Appointment, Invoice).
    Do not filter queries by hospital_id as a security/isolation boundary;
    that responsibility now lives entirely in auth/ownership checks
    (current_user["user_id"], doctor.user_id, patient.user_id, etc).
    """

    @declared_attr
    def hospital_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("hospitals.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """
    Abstract base for all models.
    Provides: UUID primary key, timestamps, soft delete.
    """

    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )