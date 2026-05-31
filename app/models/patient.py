from sqlalchemy import Column, String, Date, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import BloodGroup, Gender
import sqlalchemy as sa


class Patient(BaseModel, HospitalScopedMixin):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patient_user_id", "user_id"),
        Index("ix_patient_hospital", "hospital_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    name = Column(String(255), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(sa.Enum(Gender), nullable=True)
    blood_group = Column(sa.Enum(BloodGroup), default=BloodGroup.UNKNOWN)
    address = Column(Text, nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    allergies = Column(Text, nullable=True)
    medical_notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="patient_profile", lazy="raise")
    hospital = relationship("Hospital", back_populates="patients", lazy="raise")
    appointments = relationship(
        "Appointment", back_populates="patient", lazy="raise"
    )