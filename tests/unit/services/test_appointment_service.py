from datetime import date, datetime, time, timedelta

import pytest

from app.models.enums import AppointmentStatus, AppointmentType, DayOfWeek, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule
from app.services.appointment_service import AppointmentService
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory
from tests.factories.user_factory import UserFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def slot_at(day: DayOfWeek, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(next_weekday(day), time(hour, minute))


class TestAppointmentServiceBooking:
    def test_book_appointment_success(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)

        result = AppointmentService(db).book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
                type=AppointmentType.CONSULTATION,
            ),
            patient_user_id=patient.user_id,
        )

        assert result.id is not None
        assert result.status == AppointmentStatus.SCHEDULED
        assert result.patient_id == patient.id
        assert result.token_number == 1

    def test_double_booking_same_slot_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient1 = PatientFactory.create(db, hospital.id)
        patient2 = PatientFactory.create(db, hospital.id)
        service = AppointmentService(db)

        service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient1.user_id,
        )

        with pytest.raises(ValueError, match="already booked"):
            service.book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=slot_at(DayOfWeek.MONDAY, 10),
                ),
                patient_user_id=patient2.user_id,
            )

    def test_booking_outside_hours_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)

        with pytest.raises(ValueError, match="outside doctor's working hours"):
            AppointmentService(db).book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=slot_at(DayOfWeek.MONDAY, 2),
                ),
                patient_user_id=patient.user_id,
            )

    def test_booking_on_no_schedule_day_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)

        with pytest.raises(ValueError, match="does not work on Sunday"):
            AppointmentService(db).book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=slot_at(DayOfWeek.SUNDAY, 10),
                ),
                patient_user_id=patient.user_id,
            )

    def test_token_number_increments(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        service = AppointmentService(db)

        for index, slot in enumerate(
            [
                slot_at(DayOfWeek.MONDAY, 10, 0),
                slot_at(DayOfWeek.MONDAY, 10, 15),
                slot_at(DayOfWeek.MONDAY, 10, 30),
            ],
            start=1,
        ):
            patient = PatientFactory.create(db, hospital.id)
            result = service.book(
                data=AppointmentCreate(doctor_id=doctor.id, slot_time=slot),
                patient_user_id=patient.user_id,
            )
            assert result.token_number == index


class TestAppointmentServiceMutations:
    def test_cancel_appointment(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        service = AppointmentService(db)
        appointment = service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient.user_id,
        )

        cancelled = service.cancel(
            appointment.id,
            "Patient request",
            patient.user_id,
            UserRole.PATIENT.value,
        )

        assert cancelled.status == AppointmentStatus.CANCELLED

    def test_cancel_already_cancelled_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        service = AppointmentService(db)
        appointment = service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient.user_id,
        )
        service.cancel(
            appointment.id,
            "First cancel",
            patient.user_id,
            UserRole.PATIENT.value,
        )

        with pytest.raises(ValueError, match="Cannot cancel"):
            service.cancel(
                appointment.id,
                "Second cancel",
                patient.user_id,
                UserRole.PATIENT.value,
            )

    def test_other_patient_cannot_cancel(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        other_patient = PatientFactory.create(db, hospital.id)
        appointment = AppointmentService(db).book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient.user_id,
        )

        with pytest.raises(PermissionError, match="Access denied"):
            AppointmentService(db).cancel(
                appointment.id,
                "No access",
                other_patient.user_id,
                UserRole.PATIENT.value,
            )

    def test_reschedule_appointment(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        service = AppointmentService(db)
        appointment = service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient.user_id,
        )

        rescheduled = service.reschedule(
            appointment.id,
            AppointmentReschedule(new_slot_time=slot_at(DayOfWeek.MONDAY, 11)),
            patient.user_id,
            UserRole.PATIENT.value,
        )

        assert rescheduled.slot_time == slot_at(DayOfWeek.MONDAY, 11)

    def test_doctor_cannot_cancel(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment = AppointmentService(db).book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=slot_at(DayOfWeek.MONDAY, 10),
            ),
            patient_user_id=patient.user_id,
        )

        with pytest.raises(PermissionError, match="Access denied"):
            AppointmentService(db).cancel(
                appointment.id,
                "Doctor cannot cancel",
                doctor.user_id,
                UserRole.DOCTOR.value,
            )
