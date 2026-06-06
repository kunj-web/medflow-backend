from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.doctor import Doctor, DoctorLeave, DoctorSchedule
from app.models.enums import DayOfWeek, UserRole
from app.models.user import User
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.doctor import (
    DoctorCreate,
    DoctorResponse,
    DoctorUpdate,
    LeaveCreate,
    LeaveResponse,
    ScheduleCreate,
    ScheduleResponse,
    SlotResponse,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams


class DoctorService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.doctor_repo = DoctorRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, hospital_id: UUID, payload: DoctorCreate) -> DoctorResponse:
        """Create a User (role=DOCTOR) + Doctor record in one transaction."""
        existing = (
            self.db.query(User)
            .filter(User.phone == payload.phone, User.deleted_at.is_(None))
            .first()
        )
        if existing:
            raise ValueError("A user with this phone number already exists")

        user = User(
            hospital_id=hospital_id,
            role=UserRole.DOCTOR,
            phone=payload.phone,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.flush()  # get user.id without committing

        doctor = Doctor(
            hospital_id=hospital_id,
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            gender=payload.gender,
            phone=payload.phone,
            email=payload.email,
            specialization=payload.specialization,
            qualification=payload.qualification,
            registration_number=payload.registration_number,
            experience_years=payload.experience_years,
            consultation_fee=payload.consultation_fee,
        )
        self.db.add(doctor)
        self.db.commit()
        self.db.refresh(doctor)
        return DoctorResponse.model_validate(doctor)

    def get_by_id(self, hospital_id: UUID, doctor_id: UUID) -> DoctorResponse:
        doctor = self.doctor_repo.get_by_id_with_relations(doctor_id)
        if not doctor or doctor.hospital_id != hospital_id:
            raise LookupError("Doctor not found")
        return DoctorResponse.model_validate(doctor)

    def list_all(
        self,
        hospital_id: UUID,
        params: PaginationParams,
        specialization: str | None = None,
    ) -> PaginatedResponse[DoctorResponse]:
        if specialization:
            doctors, total = self.doctor_repo.get_by_specialization(
                hospital_id, specialization, params
            )
        else:
            doctors, total = self.doctor_repo.get_all_with_schedules(
                hospital_id, params
            )
        items = [DoctorResponse.model_validate(d) for d in doctors]
        return PaginatedResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    def update(
        self, hospital_id: UUID, doctor_id: UUID, payload: DoctorUpdate
    ) -> DoctorResponse:
        doctor = self._get_or_404(hospital_id, doctor_id)
        update_data = payload.model_dump(exclude_unset=True)

        # Keep User.phone / User.email in sync
        if "phone" in update_data or "email" in update_data:
            user = self.db.get(User, doctor.user_id)
            if user:
                if "phone" in update_data:
                    user.phone = update_data["phone"]
                if "email" in update_data:
                    user.email = update_data["email"]

        for field, value in update_data.items():
            setattr(doctor, field, value)

        self.db.commit()
        self.db.refresh(doctor)
        return DoctorResponse.model_validate(doctor)

    def delete(self, hospital_id: UUID, doctor_id: UUID) -> None:
        doctor = self._get_or_404(hospital_id, doctor_id)
        self.doctor_repo.soft_delete(doctor)
        self.db.commit()

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    def set_schedule(
        self, hospital_id: UUID, doctor_id: UUID, payload: ScheduleCreate
    ) -> ScheduleResponse:
        """Upsert a schedule entry for a given day. Replaces any existing entry."""
        doctor = self._get_or_404(hospital_id, doctor_id)

        existing = self.doctor_repo.get_schedule_for_day(doctor_id, payload.day_of_week)
        if existing:
            existing.start_time = payload.start_time
            existing.end_time = payload.end_time
            existing.slot_duration_minutes = payload.slot_duration_minutes
            self.db.commit()
            self.db.refresh(existing)
            return ScheduleResponse.model_validate(existing)

        schedule = DoctorSchedule(
            doctor_id=doctor.id,
            hospital_id=hospital_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            slot_duration_minutes=payload.slot_duration_minutes,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return ScheduleResponse.model_validate(schedule)

    def delete_schedule(
        self, hospital_id: UUID, doctor_id: UUID, day: DayOfWeek
    ) -> None:
        self._get_or_404(hospital_id, doctor_id)
        schedule = self.doctor_repo.get_schedule_for_day(doctor_id, day)
        if not schedule:
            raise LookupError(f"No schedule found for {day.value}")
        self.db.delete(schedule)
        self.db.commit()

    # ------------------------------------------------------------------
    # Leave management
    # ------------------------------------------------------------------

    def add_leave(
        self, hospital_id: UUID, doctor_id: UUID, payload: LeaveCreate
    ) -> LeaveResponse:
        doctor = self._get_or_404(hospital_id, doctor_id)

        if payload.leave_date < date.today():
            raise ValueError("Cannot mark leave for a past date")

        existing = self.doctor_repo.get_leave_for_date(doctor_id, payload.leave_date)
        if existing:
            raise ValueError(f"Leave already marked for {payload.leave_date}")

        leave = DoctorLeave(
            doctor_id=doctor.id,
            hospital_id=hospital_id,
            leave_date=payload.leave_date,
            reason=payload.reason,
        )
        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)
        return LeaveResponse.model_validate(leave)

    def cancel_leave(
        self, hospital_id: UUID, doctor_id: UUID, leave_date: date
    ) -> None:
        self._get_or_404(hospital_id, doctor_id)
        leave = self.doctor_repo.get_leave_for_date(doctor_id, leave_date)
        if not leave:
            raise LookupError(f"No leave found for {leave_date}")
        self.db.delete(leave)
        self.db.commit()

    # ------------------------------------------------------------------
    # Slot generation
    # ------------------------------------------------------------------

    def get_slots(
        self, hospital_id: UUID, doctor_id: UUID, target_date: date
    ) -> list[SlotResponse]:
        """
        Return all slots for a doctor on a given date, each marked
        available or taken.

        Algorithm:
        1. Look up the doctor's schedule for that weekday.
        2. If no schedule or doctor is on leave → return empty list.
        3. Generate every slot between start_time and end_time.
        4. Fetch booked (non-cancelled) appointments for that date.
        5. Mark each slot available or not.
        """
        self._get_or_404(hospital_id, doctor_id)

        # Map Python weekday (Mon=0) → DayOfWeek enum
        py_to_enum = {
            0: DayOfWeek.MONDAY,
            1: DayOfWeek.TUESDAY,
            2: DayOfWeek.WEDNESDAY,
            3: DayOfWeek.THURSDAY,
            4: DayOfWeek.FRIDAY,
            5: DayOfWeek.SATURDAY,
            6: DayOfWeek.SUNDAY,
        }
        day_enum = py_to_enum[target_date.weekday()]

        schedule = self.doctor_repo.get_schedule_for_day(doctor_id, day_enum)
        if not schedule:
            return []

        on_leave = self.doctor_repo.get_leave_for_date(doctor_id, target_date)
        if on_leave:
            return []

        # Build set of taken datetimes from existing appointments
        booked_appointments = self.appointment_repo.get_doctor_appointments_for_date(
            doctor_id, target_date
        )
        taken: set[datetime] = {appt.slot_time for appt in booked_appointments}

        # Generate slots
        slots: list[SlotResponse] = []
        slot_delta = timedelta(minutes=schedule.slot_duration_minutes)
        current = datetime.combine(target_date, schedule.start_time)
        end = datetime.combine(target_date, schedule.end_time)

        while current + slot_delta <= end:
            slots.append(
                SlotResponse(
                    datetime=current.isoformat(),
                    is_available=current not in taken,
                )
            )
            current += slot_delta

        return slots

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, hospital_id: UUID, doctor_id: UUID) -> Doctor:
        doctor = self.doctor_repo.get_by_id_with_relations(doctor_id)
        if not doctor or doctor.hospital_id != hospital_id or doctor.deleted_at:
            raise LookupError("Doctor not found")
        return doctor
