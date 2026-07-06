from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.doctor import Doctor, DoctorLeave, DoctorSchedule
from app.models.enums import AccountStatus, DayOfWeek
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.pagination import PaginationParams


class DoctorRepository(BaseRepository[Doctor]):
    def __init__(self, db: Session):
        super().__init__(Doctor, db)

    @staticmethod
    def _with_relations(query):
        return query.options(joinedload(Doctor.schedules), joinedload(Doctor.user))

    def get_by_id_with_relations(self, id: UUID) -> Doctor | None:
        return (
            self._with_relations(self.db.query(Doctor))
            .filter(Doctor.id == id, Doctor.deleted_at.is_(None))
            .first()
        )

    def get_public_by_id(self, id: UUID) -> Doctor | None:
        return (
            self._with_relations(self.db.query(Doctor))
            .join(User, Doctor.user_id == User.id)
            .filter(
                Doctor.id == id,
                Doctor.is_active.is_(True),
                Doctor.deleted_at.is_(None),
                User.status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )

    def search_public(
        self,
        params: PaginationParams,
        specialization: str | None = None,
        hospital_id: UUID | None = None,
        city: str | None = None,
    ) -> tuple[list[Doctor], int]:
        query = (
            self._with_relations(self.db.query(Doctor))
            .join(User, Doctor.user_id == User.id)
            .filter(
                Doctor.is_active.is_(True),
                Doctor.deleted_at.is_(None),
                User.status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        if specialization:
            query = query.filter(Doctor.specialization.ilike(f"%{specialization}%"))
        if hospital_id:
            query = query.filter(Doctor.hospital_id == hospital_id)
        if city:
            query = query.filter(Doctor.clinic_city.ilike(f"%{city}%"))

        total = query.count()
        doctors = (
            query.order_by(Doctor.created_at.desc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .all()
        )
        return doctors, total

    def get_schedule_for_day(
        self, doctor_id: UUID, day: DayOfWeek
    ) -> DoctorSchedule | None:
        return (
            self.db.query(DoctorSchedule)
            .filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.day_of_week == day,
                DoctorSchedule.is_active.is_(True),
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

    def get_blocks_for_date(self, doctor_id: UUID, block_date: date):
        from app.models.doctor import DoctorSlotBlock

        return (
            self.db.query(DoctorSlotBlock)
            .filter(
                DoctorSlotBlock.doctor_id == doctor_id,
                DoctorSlotBlock.block_date == block_date,
                DoctorSlotBlock.deleted_at.is_(None),
            )
            .order_by(DoctorSlotBlock.start_time)
            .all()
        )
