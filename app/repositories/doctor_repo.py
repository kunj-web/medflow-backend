from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.doctor import Doctor, DoctorLeave, DoctorSchedule
from app.models.enums import DayOfWeek
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):
    def __init__(self, db: Session):
        super().__init__(Doctor, db)

    def get_by_id_with_relations(self, id: UUID) -> Doctor | None:
        return (
            self.db.query(Doctor)
            .options(
                joinedload(Doctor.schedules),
                joinedload(Doctor.user),
            )
            .filter(
                Doctor.id == id,
                Doctor.deleted_at.is_(None),
            )
            .first()
        )

    def get_all_with_schedules(self, hospital_id: UUID) -> list[Doctor]:
        return (
            self.db.query(Doctor)
            .options(
                joinedload(Doctor.schedules),
                joinedload(Doctor.user),
            )
            .filter(
                Doctor.hospital_id == hospital_id,
                Doctor.deleted_at.is_(None),
                Doctor.is_available,
            )
            .all()
        )

    def get_by_specialization(
        self, hospital_id: UUID, specialization: str
    ) -> list[Doctor]:
        return (
            self.db.query(Doctor)
            .options(joinedload(Doctor.schedules))
            .filter(
                Doctor.hospital_id == hospital_id,
                Doctor.specialization.ilike(f"%{specialization}%"),
                Doctor.deleted_at.is_(None),
            )
            .all()
        )

    def get_schedule_for_day(
        self, doctor_id: UUID, day: DayOfWeek
    ) -> DoctorSchedule | None:
        return (
            self.db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.day_of_week == day,
                DoctorSchedule.is_active,
                DoctorSchedule.deleted_at.is_(None),
            )
            .first()
        )

    def get_leave_for_date(
        self, doctor_id: UUID, leave_date: date
    ) -> DoctorLeave | None:
        return (
            self.db.query(DoctorLeave)
            .filter(
                DoctorLeave.doctor_id == doctor_id,
                DoctorLeave.leave_date == leave_date,
                DoctorLeave.deleted_at.is_(None),
            )
            .first()
        )
