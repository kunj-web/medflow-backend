import sqlalchemy as sa
from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import BaseModel
from app.models.enums import NotificationType


class Notification(BaseModel):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user_read", "user_id", "is_read"),
        Index("ix_notification_appointment", "appointment_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    type = Column(sa.Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    data = Column(sa.JSON, nullable=True)   # extra metadata for deep links

    # Relationships
    user = relationship("User", back_populates="notifications", lazy="raise")
    appointment = relationship(
        "Appointment", back_populates="notifications", lazy="raise"
    )


class UserDevice(BaseModel):
    __tablename__ = "user_devices"
    __table_args__ = (
        Index("ix_device_user", "user_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    fcm_token = Column(Text, nullable=False)
    device_info = Column(String(255), nullable=True)   # browser/OS string
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="devices", lazy="raise")
