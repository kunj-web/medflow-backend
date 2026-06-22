from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.repositories.base import BaseRepository, PaginatedResult


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self, db: Session):
        super().__init__(Appointment, db)

    @staticmethod
    def _with_relations(query):
        return query.options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor),
            joinedload(Appointment.invoice),
        )

    def get_by_id_with_relations(self, id: UUID) -> Appointment | None:
        return (
            self._with_relations(self.db.query(Appointment))
            .filter(Appointment.id == id, Appointment.deleted_at.is_(None))
            .first()
        )

    def get_paginated_for_patient_user(
        self, user_id: UUID, page: int, page_size: int
    ) -> PaginatedResult:
        query = self._with_relations(self.db.query(Appointment)).join(
            Patient, Appointment.patient_id == Patient.id
        ).filter(
            Patient.user_id == user_id,
            Patient.deleted_at.is_(None),
            Appointment.deleted_at.is_(None),
        )
        return self._paginate(query, page, page_size)

    def get_paginated_for_doctor_user(
        self, user_id: UUID, page: int, page_size: int
    ) -> PaginatedResult:
        query = self._with_relations(self.db.query(Appointment)).join(
            Doctor, Appointment.doctor_id == Doctor.id
        ).filter(
            Doctor.user_id == user_id,
            Doctor.deleted_at.is_(None),
            Appointment.deleted_at.is_(None),
        )
        return self._paginate(query, page, page_size)

    def get_paginated_all(self, page: int, page_size: int) -> PaginatedResult:
        query = self._with_relations(self.db.query(Appointment)).filter(
            Appointment.deleted_at.is_(None)
        )
        return self._paginate(query, page, page_size)

    @staticmethod
    def _paginate(query, page: int, page_size: int) -> PaginatedResult:
        total = query.count()
        data = (
            query.order_by(Appointment.slot_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResult(data, total, page, page_size)

    def get_doctor_appointments_for_date(
        self, doctor_id: UUID, target_date: date
    ) -> list[Appointment]:
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.patient))
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_time >= datetime.combine(target_date, datetime.min.time()),
                Appointment.slot_time < datetime.combine(target_date, datetime.max.time()),
                Appointment.status.notin_(
                    [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                ),
                Appointment.deleted_at.is_(None),
            )
            .order_by(Appointment.slot_time)
            .all()
        )

    def get_all_for_date(self, target_date: date) -> list[Appointment]:
        return (
            self._with_relations(self.db.query(Appointment))
            .filter(
                Appointment.slot_time >= datetime.combine(target_date, datetime.min.time()),
                Appointment.slot_time < datetime.combine(target_date, datetime.max.time()),
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.deleted_at.is_(None),
            )
            .order_by(Appointment.slot_time)
            .all()
        )

    def get_slot_if_taken(
        self, doctor_id: UUID, slot_time: datetime
    ) -> Appointment | None:
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_time == slot_time,
                Appointment.status.notin_(
                    [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                ),
                Appointment.deleted_at.is_(None),
            )
            .first()
        )
