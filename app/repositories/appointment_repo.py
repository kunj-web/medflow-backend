from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus
from app.repositories.base import BaseRepository, PaginatedResult


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self, db: Session):
        super().__init__(Appointment, db)

    def get_by_id_with_relations(self, id: UUID) -> Appointment | None:
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor),
                joinedload(Appointment.invoice),
            )
            .filter(
                Appointment.id == id,
                Appointment.deleted_at.is_(None),
            )
            .first()
        )

    def get_doctor_appointments_for_date(
        self, doctor_id: UUID, date: date
    ) -> list[Appointment]:
        """Used for slot availability and queue management."""
        return (
            self.db.query(Appointment)
            .options(joinedload(Appointment.patient))
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_time >= datetime.combine(date, datetime.min.time()),
                Appointment.slot_time < datetime.combine(date, datetime.max.time()),
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                ]),
                Appointment.deleted_at.is_(None),
            )
            .order_by(Appointment.slot_time)
            .all()
        )

    def get_slot_if_taken(
        self, doctor_id: UUID, slot_time: datetime
    ) -> Appointment | None:
        """Check for double booking."""
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_time == slot_time,
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                ]),
                Appointment.deleted_at.is_(None),
            )
            .first()
        )

    def get_hospital_queue_for_date(
        self, hospital_id: UUID, date: date
    ) -> list[Appointment]:
        """Today's queue for staff dashboard."""
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor),
            )
            .filter(
                Appointment.hospital_id == hospital_id,
                Appointment.slot_time >= datetime.combine(date, datetime.min.time()),
                Appointment.slot_time < datetime.combine(date, datetime.max.time()),
                Appointment.status.notin_([AppointmentStatus.CANCELLED]),
                Appointment.deleted_at.is_(None),
            )
            .order_by(Appointment.slot_time)
            .all()
        )

    def get_paginated_with_relations(
        self,
        hospital_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: list = None,
    ) -> PaginatedResult:
        query = (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor),
            )
            .filter(
                Appointment.hospital_id == hospital_id,
                Appointment.deleted_at.is_(None),
            )
        )
        if filters:
            for f in filters:
                query = query.filter(f)

        total = query.count()
        data = (
            query
            .order_by(Appointment.slot_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResult(data=data, total=total, page=page, page_size=page_size)
