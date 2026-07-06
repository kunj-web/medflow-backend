from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.doctor import Doctor, DoctorLeave, DoctorSchedule, DoctorSlotBlock
from app.models.enums import DayOfWeek
from app.models.user import User
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.doctor import (
    DoctorResponse,
    DoctorUpdate,
    LeaveCreate,
    LeaveResponse,
    ScheduleCreate,
    ScheduleResponse,
    SlotBlockCreate,
    SlotBlockResponse,
    SlotResponse,
)
from app.schemas.pagination import PaginatedResponse, PaginationParams


class DoctorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.doctor_repo = DoctorRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    def get_public_by_id(self, doctor_id: UUID) -> DoctorResponse:
        doctor = self.doctor_repo.get_public_by_id(doctor_id)
        if not doctor:
            raise LookupError("Doctor not found")
        return DoctorResponse.model_validate(doctor)

    def list_public(
        self,
        params: PaginationParams,
        specialization: str | None = None,
        hospital_id: UUID | None = None,
        city: str | None = None,
    ) -> PaginatedResponse[DoctorResponse]:
        doctors, total = self.doctor_repo.search_public(
            params, specialization, hospital_id, city
        )
        return PaginatedResponse(
            data=[DoctorResponse.model_validate(doctor) for doctor in doctors],
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    def update(
        self,
        doctor_id: UUID,
        payload: DoctorUpdate,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> DoctorResponse:
        doctor = self._get_owned_or_admin(
            doctor_id, actor_user_id, is_website_admin
        )
        update_data = payload.model_dump(exclude_unset=True)
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
        return DoctorResponse.model_validate(
            self.doctor_repo.get_by_id_with_relations(doctor.id)
        )

    def delete(self, doctor_id: UUID) -> None:
        doctor = self._get_or_404(doctor_id)
        self.doctor_repo.soft_delete(doctor)
        self.db.commit()

    def set_schedule(
        self,
        doctor_id: UUID,
        payload: ScheduleCreate,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> ScheduleResponse:
        doctor = self._get_owned_or_admin(
            doctor_id, actor_user_id, is_website_admin
        )
        existing = self.doctor_repo.get_schedule_for_day(
            doctor_id, payload.day_of_week
        )
        if existing:
            existing.start_time = payload.start_time
            existing.end_time = payload.end_time
            existing.slot_duration_minutes = payload.slot_duration_minutes
            self.db.commit()
            self.db.refresh(existing)
            return ScheduleResponse.model_validate(existing)

        schedule = DoctorSchedule(
            doctor_id=doctor.id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            slot_duration_minutes=payload.slot_duration_minutes,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return ScheduleResponse.model_validate(schedule)

    def list_schedules(
        self,
        doctor_id: UUID,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> list[ScheduleResponse]:
        doctor = self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        schedules = sorted(
            [schedule for schedule in doctor.schedules if schedule.deleted_at is None],
            key=lambda schedule: list(DayOfWeek).index(schedule.day_of_week),
        )
        return [ScheduleResponse.model_validate(schedule) for schedule in schedules]

    def replace_weekly_schedule(
        self,
        doctor_id: UUID,
        payload: list[ScheduleCreate],
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> list[ScheduleResponse]:
        doctor = self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        existing_by_day = {
            schedule.day_of_week: schedule
            for schedule in doctor.schedules
            if schedule.deleted_at is None
        }
        requested_by_day = {schedule.day_of_week: schedule for schedule in payload}

        for day, schedule in existing_by_day.items():
            if day not in requested_by_day:
                self.db.delete(schedule)

        for day, schedule_payload in requested_by_day.items():
            existing = existing_by_day.get(day)
            if existing:
                existing.start_time = schedule_payload.start_time
                existing.end_time = schedule_payload.end_time
                existing.slot_duration_minutes = schedule_payload.slot_duration_minutes
                existing.is_active = True
                continue

            self.db.add(
                DoctorSchedule(
                    doctor_id=doctor.id,
                    day_of_week=schedule_payload.day_of_week,
                    start_time=schedule_payload.start_time,
                    end_time=schedule_payload.end_time,
                    slot_duration_minutes=schedule_payload.slot_duration_minutes,
                )
            )

        self.db.commit()
        return self.list_schedules(doctor_id, actor_user_id, is_website_admin)

    def delete_schedule(
        self,
        doctor_id: UUID,
        day: DayOfWeek,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> None:
        self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        schedule = self.doctor_repo.get_schedule_for_day(doctor_id, day)
        if not schedule:
            raise LookupError(f"No schedule found for {day.value}")
        self.db.delete(schedule)
        self.db.commit()

    def add_leave(
        self,
        doctor_id: UUID,
        payload: LeaveCreate,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> LeaveResponse:
        doctor = self._get_owned_or_admin(
            doctor_id, actor_user_id, is_website_admin
        )
        if payload.leave_date < date.today():
            raise ValueError("Cannot mark leave for a past date")
        if self.doctor_repo.get_leave_for_date(doctor_id, payload.leave_date):
            raise ValueError(f"Leave already marked for {payload.leave_date}")

        leave = DoctorLeave(
            doctor_id=doctor.id,
            leave_date=payload.leave_date,
            reason=payload.reason,
        )
        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)
        return LeaveResponse.model_validate(leave)

    def list_leaves(
        self,
        doctor_id: UUID,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> list[LeaveResponse]:
        self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        leaves = (
            self.db.query(DoctorLeave)
            .filter(DoctorLeave.doctor_id == doctor_id, DoctorLeave.deleted_at.is_(None))
            .order_by(DoctorLeave.leave_date)
            .all()
        )
        return [LeaveResponse.model_validate(leave) for leave in leaves]

    def cancel_leave(
        self,
        doctor_id: UUID,
        leave_date: date,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> None:
        self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        leave = self.doctor_repo.get_leave_for_date(doctor_id, leave_date)
        if not leave:
            raise LookupError(f"No leave found for {leave_date}")
        self.db.delete(leave)
        self.db.commit()

    def list_slot_blocks(
        self,
        doctor_id: UUID,
        target_date: date,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> list[SlotBlockResponse]:
        self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        blocks = self.doctor_repo.get_blocks_for_date(doctor_id, target_date)
        return [SlotBlockResponse.model_validate(block) for block in blocks]

    def add_slot_block(
        self,
        doctor_id: UUID,
        payload: SlotBlockCreate,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> SlotBlockResponse:
        doctor = self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        if payload.block_date < date.today():
            raise ValueError("Cannot block a past date")
        self._ensure_block_does_not_cover_existing_appointment(doctor.id, payload)

        block = DoctorSlotBlock(
            doctor_id=doctor.id,
            block_date=payload.block_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            reason=payload.reason,
        )
        self.db.add(block)
        self.db.commit()
        self.db.refresh(block)
        return SlotBlockResponse.model_validate(block)

    def delete_slot_block(
        self,
        doctor_id: UUID,
        block_id: UUID,
        actor_user_id: UUID,
        is_website_admin: bool,
    ) -> None:
        self._get_owned_or_admin(doctor_id, actor_user_id, is_website_admin)
        block = (
            self.db.query(DoctorSlotBlock)
            .filter(
                DoctorSlotBlock.id == block_id,
                DoctorSlotBlock.doctor_id == doctor_id,
                DoctorSlotBlock.deleted_at.is_(None),
            )
            .first()
        )
        if not block:
            raise LookupError("Slot block not found")
        self.db.delete(block)
        self.db.commit()

    def get_slots(self, doctor_id: UUID, target_date: date) -> list[SlotResponse]:
        self.get_public_by_id(doctor_id)
        if target_date <= date.today():
            return []

        day_enum = list(DayOfWeek)[target_date.weekday()]
        schedule = self.doctor_repo.get_schedule_for_day(doctor_id, day_enum)
        if not schedule or self.doctor_repo.get_leave_for_date(doctor_id, target_date):
            return []

        appointments = self.appointment_repo.get_doctor_appointments_for_date(
            doctor_id, target_date
        )
        taken = {
            appointment.slot_time.replace(tzinfo=None)
            for appointment in appointments
        }
        blocks = self.doctor_repo.get_blocks_for_date(doctor_id, target_date)
        delta = timedelta(minutes=schedule.slot_duration_minutes)
        current = datetime.combine(target_date, schedule.start_time)
        end = datetime.combine(target_date, schedule.end_time)
        slots = []
        while current + delta <= end:
            block = self._block_for_slot(current, blocks)
            slots.append(
                SlotResponse(
                    datetime=current.isoformat(),
                    is_available=current not in taken and block is None,
                    block_id=block.id if block else None,
                    block_reason=block.reason if block else None,
                )
            )
            current += delta
        return slots

    def _get_or_404(self, doctor_id: UUID) -> Doctor:
        doctor = self.doctor_repo.get_by_id_with_relations(doctor_id)
        if not doctor:
            raise LookupError("Doctor not found")
        return doctor

    def _get_owned_or_admin(
        self, doctor_id: UUID, actor_user_id: UUID, is_website_admin: bool
    ) -> Doctor:
        doctor = self._get_or_404(doctor_id)
        if not is_website_admin and doctor.user_id != actor_user_id:
            raise PermissionError("Access denied")
        return doctor

    def _ensure_block_does_not_cover_existing_appointment(
        self, doctor_id: UUID, payload: SlotBlockCreate
    ) -> None:
        appointments = self.appointment_repo.get_doctor_appointments_for_date(
            doctor_id, payload.block_date
        )
        for appointment in appointments:
            slot_time = appointment.slot_time.replace(tzinfo=None).time()
            if payload.start_time <= slot_time < payload.end_time:
                raise ValueError("Cannot block a time that already has an appointment")

    @staticmethod
    def _block_for_slot(current: datetime, blocks: list[DoctorSlotBlock]) -> DoctorSlotBlock | None:
        slot_time = current.time()
        for block in blocks:
            if block.start_time <= slot_time < block.end_time:
                return block
        return None
