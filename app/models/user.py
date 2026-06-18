import sqlalchemy as sa
from sqlalchemy import Boolean, Column, Index, String
from sqlalchemy.orm import relationship

from app.db.base import BaseModel
from app.models.enums import AccountStatus, UserRole


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_user_email", "email", unique=True),
        Index("ix_user_phone", "phone"),
        Index("ix_user_role", "role"),
        Index("ix_user_status", "status"),
    )

    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(sa.Enum(UserRole), nullable=False)

    # Single source of truth for approval/lifecycle state.
    # PATIENT -> ACTIVE on creation. DOCTOR -> PENDING until website-admin
    # approval. WEBSITE_ADMIN -> never created via /register; only via
    # seed script or an existing super admin.
    status = Column(
        sa.Enum(AccountStatus),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )

    # True only for the bootstrapped super admin created by
    # scripts/seed_admin.py. Grants admin-of-admins capability.
    is_super_admin = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Relationships
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
    