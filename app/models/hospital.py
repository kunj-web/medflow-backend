from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class Hospital(BaseModel):
    __tablename__ = "hospitals"

    name = Column(String(255), nullable=False)
    logo_url = Column(Text, nullable=True)
    primary_color = Column(String(7), default="#0066CC")
    secondary_color = Column(String(7), default="#E8F4FD")
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    currency = Column(String(3), default="INR")
    timezone = Column(String(50), default="Asia/Kolkata")
    is_active = Column(Boolean, default=True)

    # Relationships
    features = relationship(
        "HospitalFeature",
        back_populates="hospital",
        lazy="raise",
    )
    users = relationship(
        "User",
        back_populates="hospital",
        lazy="raise",
    )
    doctors = relationship(
        "Doctor",
        back_populates="hospital",
        lazy="raise",
    )
    patients = relationship(
        "Patient",
        back_populates="hospital",
        lazy="raise",
    )


class HospitalFeature(BaseModel):
    __tablename__ = "hospital_features"

    hospital_id = Column(
        "hospital_id",
        __import__("sqlalchemy").ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )
    feature_key = Column(String(100), nullable=False)
    is_enabled = Column(Boolean, default=True)

    # Relationships
    hospital = relationship(
        "Hospital",
        back_populates="features",
        lazy="raise",
    )
