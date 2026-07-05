import sqlalchemy as sa
from sqlalchemy import Boolean, Column, ForeignKey, Index, Numeric, String, Text, Time, Uuid
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, HospitalScopedMixin
from app.models.enums import DayOfWeek, Gender, WorkType


class Doctor(BaseModel, HospitalScopedMixin):
    __tablename__ = "doctors"
    __table_args__ = (
        Index("ix_doctor_user_id", "user_id"),
        Index("ix_doctor_specialization", "specialization"),
        Index("ix_doctor_hospital", "hospital_id"),
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    gender = Column(sa.Enum(Gender), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    specialization = Column(String(255), nullable=False)
    qualification = Column(String(255), nullable=True)
    registration_number = Column(String(100), nullable=True)
    experience_years = Column(sa.Integer, default=0)
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=0)

    # NOTE: is_active here means "available for bookings", distinct from
    # User.status which gates whether the doctor is approved/visible at all.
    # A doctor can be User.status=ACTIVE but is_active=False (on break,
    # temporarily not taking bookings) without losing platform approval.
    is_active = Column(Boolean, default=True)

    # --- Affiliation ---------------------------------------------------
    work_type = Column(sa.Enum(WorkType), nullable=False, default=WorkType.HOSPITAL)

    # Populated when work_type = CLINIC
    clinic_name = Column(String(255), nullable=True)
    clinic_city = Column(String(100), nullable=True)
    clinic_address = Column(Text, nullable=True)

    # Populated when work_type = HOSPITAL and doctor selected an existing
    # hospital from the dropdown at registration time.
    # hospital_id (from HospitalScopedMixin) is nullable — null until a
    # website admin links it during approval.

    # Populated when work_type = HOSPITAL and doctor typed a hospital
    # manually instead of selecting one. Cleared once a website admin
    # links/creates the real Hospital row and sets hospital_id.
    pending_hospital_name = Column(String(255), nullable=True)
    pending_hospital_city = Column(String(100), nullable=True)
    pending_hospital_state = Column(String(100), nullable=True)

    # Relationships
    user = relationship("User", back_populates="doctor_profile", lazy="raise")
    hospital = relationship("Hospital", back_populates="doctors", lazy="raise")
    schedules = relationship("DoctorSchedule", back_populates="doctor", lazy="raise")
    leaves = relationship("DoctorLeave", back_populates="doctor", lazy="raise")
    appointments = relationship("Appointment", back_populates="doctor", lazy="raise")


class DoctorSchedule(BaseModel):
    __tablename__ = "doctor_schedules"
    __table_args__ = (
        Index("ix_schedule_doctor_day", "doctor_id", "day_of_week", unique=True),
    )

    doctor_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week = Column(sa.Enum(DayOfWeek), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(sa.Integer, default=10)
    is_active = Column(Boolean, default=True)

    # Relationships
    doctor = relationship("Doctor", back_populates="schedules", lazy="raise")


class DoctorLeave(BaseModel):
    __tablename__ = "doctor_leaves"
    __table_args__ = (
        Index("ix_leave_doctor_date", "doctor_id", "leave_date"),
    )

    doctor_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    leave_date = Column(sa.Date, nullable=False)
    reason = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False)

    # Relationships
    doctor = relationship("Doctor", back_populates="leaves", lazy="raise")
    
