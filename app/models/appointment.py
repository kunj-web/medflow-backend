from sqlalchemy import Column, DateTime, Text, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import AppointmentStatus, AppointmentType
import sqlalchemy as sa


class Appointment(BaseModel, HospitalScopedMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        # Most common query: all appointments for a hospital on a given day
        Index("ix_appointment_hospital_slot", "hospital_id", "slot_time"),
        # Doctor's schedule view
        Index("ix_appointment_doctor_status", "doctor_id", "status"),
        # Patient's appointment history
        Index("ix_appointment_patient", "patient_id"),
        # Prevent double booking same doctor at same slot
        sa.UniqueConstraint(
            "doctor_id", "slot_time",
            name="uq_doctor_slot",
        ),
    )

    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    doctor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        sa.Enum(AppointmentStatus),
        nullable=False,
        default=AppointmentStatus.SCHEDULED,
    )
    type = Column(
        sa.Enum(AppointmentType),
        nullable=False,
        default=AppointmentType.CONSULTATION,
    )
    chief_complaint = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)          # doctor's notes post-consult
    cancellation_reason = Column(Text, nullable=True)
    token_number = Column(sa.Integer, nullable=True)    # queue token

    # Relationships
    patient = relationship("Patient", back_populates="appointments", lazy="raise")
    doctor = relationship("Doctor", back_populates="appointments", lazy="raise")
    invoice = relationship(
        "Invoice", back_populates="appointment", uselist=False, lazy="raise"
    )
    notifications = relationship(
        "Notification", back_populates="appointment", lazy="raise"
    )