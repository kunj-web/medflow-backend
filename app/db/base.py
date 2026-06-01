import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import func


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
        self.deleted_at = datetime.now(timezone.utc)


class HospitalScopedMixin:
    """Every tenant-scoped model must include hospital_id."""

    @declared_attr
    def hospital_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("hospitals.id", ondelete="RESTRICT"),
            nullable=False,
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