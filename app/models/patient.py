import sqlalchemy as sa
from sqlalchemy import Column, Date, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import BaseModel
from app.models.enums import BloodGroup, Gender


class Patient(BaseModel):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patient_user_id", "user_id"),
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    gender = Column(sa.Enum(Gender), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    blood_group = Column(sa.Enum(BloodGroup), nullable=True)
    height = Column(sa.Float, nullable=True)
    weight = Column(sa.Float, nullable=True)
    allergies = Column(Text, nullable=True)
    existing_conditions = Column(Text, nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    # Relationships
    user = relationship("User", back_populates="patient_profile", lazy="raise")
    
    appointments = relationship("Appointment", back_populates="patient", lazy="raise")
