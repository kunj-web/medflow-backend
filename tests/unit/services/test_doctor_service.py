from datetime import date, time, timedelta
from uuid import uuid4

import pytest

from app.models.doctor import DoctorLeave
from app.models.enums import AccountStatus, DayOfWeek, UserRole
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.doctor import LeaveCreate, ScheduleCreate
from app.schemas.pagination import PaginationParams
from app.services.doctor_service import DoctorService
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.user_factory import UserFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


class TestDoctorPublicAccess:
    def test_list_public_returns_only_active_approved_doctors(self, db, hospital):
        active = DoctorFactory.create(db, hospital.id, specialization="Cardiologist")
        inactive = DoctorFactory.create(db, hospital.id, is_active=False)
        pending_user = UserFactory.create(
            db,
            hospital.id,
            role=UserRole.DOCTOR,
            status=AccountStatus.PENDING,
        )
        pending = DoctorFactory.create(db, hospital.id, user_id=pending_user.id)

        result = DoctorService(db).list_public(PaginationParams(page=1, page_size=20))

        ids = {doctor.id for doctor in result.data}
        assert active.id in ids
        assert inactive.id not in ids
        assert pending.id not in ids

    def test_get_public_by_id_rejects_pending_doctor(self, db, hospital):
        pending_user = UserFactory.create(
            db,
            hospital.id,
            role=UserRole.DOCTOR,
            status=AccountStatus.PENDING,
        )
        doctor = DoctorFactory.create(db, hospital.id, user_id=pending_user.id)

        with pytest.raises(LookupError, match="Doctor not found"):
            DoctorService(db).get_public_by_id(doctor.id)


class TestDoctorSchedule:
    def test_admin_can_set_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        service = DoctorService(db)

        result = service.set_schedule(
            doctor.id,
            ScheduleCreate(
                day_of_week=DayOfWeek.SUNDAY,
                start_time=time(10, 0),
                end_time=time(14, 0),
            ),
            actor_user_id=uuid_for_admin(),
            is_website_admin=True,
        )

        assert result.day_of_week == DayOfWeek.SUNDAY
        assert result.start_time == time(10, 0)
        assert result.end_time == time(14, 0)

    def test_owner_doctor_can_overwrite_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        service = DoctorService(db)

        service.set_schedule(
            doctor.id,
            ScheduleCreate(
                day_of_week=DayOfWeek.MONDAY,
                start_time=time(8, 0),
                end_time=time(12, 0),
            ),
            actor_user_id=doctor.user_id,
            is_website_admin=False,
        )

        schedule = DoctorRepository(db).get_schedule_for_day(
            doctor.id, DayOfWeek.MONDAY
        )
        assert schedule.start_time == time(8, 0)
        assert schedule.end_time == time(12, 0)

    def test_other_doctor_cannot_set_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        other = DoctorFactory.create(db, hospital.id)

        with pytest.raises(PermissionError, match="Access denied"):
            DoctorService(db).set_schedule(
                doctor.id,
                ScheduleCreate(
                    day_of_week=DayOfWeek.SUNDAY,
                    start_time=time(10, 0),
                    end_time=time(14, 0),
                ),
                actor_user_id=other.user_id,
                is_website_admin=False,
            )

    def test_delete_schedule_removes_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        service = DoctorService(db)

        service.delete_schedule(
            doctor.id,
            DayOfWeek.MONDAY,
            actor_user_id=doctor.user_id,
            is_website_admin=False,
        )

        assert DoctorRepository(db).get_schedule_for_day(
            doctor.id, DayOfWeek.MONDAY
        ) is None


class TestDoctorLeaveAndSlots:
    def test_add_leave_rejects_past_date(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)

        with pytest.raises(ValueError, match="past date"):
            DoctorService(db).add_leave(
                doctor.id,
                LeaveCreate(leave_date=date.today() - timedelta(days=1)),
                actor_user_id=doctor.user_id,
                is_website_admin=False,
            )

    def test_leave_blocks_slots_for_that_date(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        target = next_weekday(DayOfWeek.MONDAY)
        db.add(
            DoctorLeave(
                doctor_id=doctor.id,
                leave_date=target,
                reason="Conference",
            )
        )
        db.flush()

        slots = DoctorService(db).get_slots(doctor.id, target)

        assert slots == []

    def test_get_slots_uses_schedule_duration(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        target = next_weekday(DayOfWeek.MONDAY)

        slots = DoctorService(db).get_slots(doctor.id, target)

        assert len(slots) == 32
        assert slots[0].datetime.endswith("T09:00:00")
        assert slots[0].is_available is True


def uuid_for_admin():
    return uuid4()
