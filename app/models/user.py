import sqlalchemy as sa
from sqlalchemy import Boolean, Column, Index, String
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import UserRole


class User(BaseModel, HospitalScopedMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_user_email_hospital", "email", "hospital_id", unique=True),
        Index("ix_user_phone_hospital", "phone", "hospital_id"),
        Index("ix_user_role", "role"),
    )

    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(sa.Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="users", lazy="raise")
    patient_profile = relationship(
        "Patient", back_populates="user", uselist=False, lazy="raise"
    )
    doctor_profile = relationship(
        "Doctor", back_populates="user", uselist=False, lazy="raise"
    )
    notifications = relationship(
        "Notification", back_populates="user", lazy="raise"
    )
    devices = relationship("UserDevice", back_populates="user", lazy="raise")
