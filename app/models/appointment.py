import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import AppointmentStatus, AppointmentType


class Appointment(BaseModel, HospitalScopedMixin):
    """
    hospital_id (via HospitalScopedMixin) is a SNAPSHOT, not a live
    relationship. It is copied from doctor.hospital_id at booking time
    in AppointmentService.book() and never updated afterward — even if
    the doctor later changes hospital affiliation. This preserves
    historical accuracy for reporting (e.g. "revenue by hospital").
    Nullable because clinic-based doctors have no hospital.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        # Doctor's schedule view / double-booking check
        Index("ix_appointment_doctor_status", "doctor_id", "status"),
        # Patient's appointment history
        Index("ix_appointment_patient", "patient_id"),
        # Historical reporting by hospital (nullable, sparse index is fine)
        Index("ix_appointment_hospital", "hospital_id"),
        # Prevent double booking same doctor at same slot
        sa.UniqueConstraint(
            "doctor_id", "slot_time",
            name="uq_doctor_slot",
        ),
    )

    patient_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    doctor_id = Column(
        Uuid(as_uuid=True),
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
    
