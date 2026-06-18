from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class Hospital(BaseModel):
    __tablename__ = "hospitals"

    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
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
    # NOTE: `users` relationship removed — User no longer has hospital_id.
    # Hospital is now a reference table doctors affiliate with, not a
    # tenancy root. Appointment/Invoice keep hospital_id as a historical
    # snapshot, not an active relationship requiring back_populates here.
    features = relationship(
        "HospitalFeature",
        back_populates="hospital",
        lazy="raise",
    )
    doctors = relationship(
        "Doctor",
        back_populates="hospital",
        lazy="raise",
    )


class HospitalFeature(BaseModel):
    __tablename__ = "hospital_features"

    hospital_id = Column(
        "hospital_id",
        ForeignKey("hospitals.id"),
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