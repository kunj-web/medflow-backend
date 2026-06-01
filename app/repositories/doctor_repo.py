from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.repositories.base import BaseRepository
from app.models.doctor import Doctor, DoctorSchedule, DoctorLeave
from app.models.enums import DayOfWeek
from datetime import date


class DoctorRepository(BaseRepository[Doctor]):
    def __init__(self, db: Session):
        super().__init__(Doctor, db)

    def get_by_id_with_relations(self, id: UUID) -> Optional[Doctor]:
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

    def get_all_with_schedules(self, hospital_id: UUID) -> List[Doctor]:
        return (
            self.db.query(Doctor)
            .options(
                joinedload(Doctor.schedules),
                joinedload(Doctor.user),
            )
            .filter(
                Doctor.hospital_id == hospital_id,
                Doctor.deleted_at.is_(None),
                Doctor.is_available == True,
            )
            .all()
        )

    def get_by_specialization(
        self, hospital_id: UUID, specialization: str
    ) -> List[Doctor]:
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
    ) -> Optional[DoctorSchedule]:
        return (
            self.db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.day_of_week == day,
                DoctorSchedule.is_active == True,
                DoctorSchedule.deleted_at.is_(None),
            )
            .first()
        )

    def get_leave_for_date(
        self, doctor_id: UUID, leave_date: date
    ) -> Optional[DoctorLeave]:
        return (
            self.db.query(DoctorLeave)
            .filter(
                DoctorLeave.doctor_id == doctor_id,
                DoctorLeave.leave_date == leave_date,
                DoctorLeave.deleted_at.is_(None),
            )
            .first()
        )