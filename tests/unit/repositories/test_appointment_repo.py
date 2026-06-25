from datetime import date, datetime, time, timedelta

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, AppointmentType, DayOfWeek
from app.repositories.appointment_repo import AppointmentRepository
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def slot_at(day: DayOfWeek, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(next_weekday(day), time(hour, minute))


def create_appointment(db, patient, doctor, slot_time):
    appointment = Appointment(
        hospital_id=doctor.hospital_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        slot_time=slot_time,
        end_time=slot_time + timedelta(minutes=15),
        status=AppointmentStatus.SCHEDULED,
        type=AppointmentType.CONSULTATION,
        token_number=1,
    )
    db.add(appointment)
    db.flush()
    return appointment


class TestAppointmentRepository:
    def test_get_paginated_for_patient_user(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        other_patient = PatientFactory.create(db, hospital.id)
        appointment = create_appointment(
            db, patient, doctor, slot_at(DayOfWeek.MONDAY, 10)
        )
        create_appointment(db, other_patient, doctor, slot_at(DayOfWeek.MONDAY, 11))

        result = AppointmentRepository(db).get_paginated_for_patient_user(
            patient.user_id,
            page=1,
            page_size=20,
        )

        assert result.total == 1
        assert result.data[0].id == appointment.id

    def test_get_paginated_for_doctor_user(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        other_doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment = create_appointment(
            db, patient, doctor, slot_at(DayOfWeek.MONDAY, 10)
        )
        create_appointment(db, patient, other_doctor, slot_at(DayOfWeek.MONDAY, 11))

        result = AppointmentRepository(db).get_paginated_for_doctor_user(
            doctor.user_id,
            page=1,
            page_size=20,
        )

        assert result.total == 1
        assert result.data[0].id == appointment.id

    def test_get_slot_if_taken_ignores_cancelled(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        slot = slot_at(DayOfWeek.MONDAY, 10)
        appointment = create_appointment(db, patient, doctor, slot)
        appointment.status = AppointmentStatus.CANCELLED
        db.flush()

        assert AppointmentRepository(db).get_slot_if_taken(doctor.id, slot) is None
