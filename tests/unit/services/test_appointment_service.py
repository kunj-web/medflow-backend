from datetime import UTC, datetime

import pytest

from app.models.enums import AppointmentType, UserRole
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import AppointmentService
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory
from tests.factories.user_factory import UserFactory

# Monday 10 AM — doctors have schedule Mon-Sat 9-17
VALID_SLOT = datetime(2025, 6, 2, 10, 0, 0, tzinfo=UTC)   # Monday
OUTSIDE_HOURS_SLOT = datetime(2025, 6, 2, 2, 0, 0, tzinfo=UTC)  # 2 AM
SUNDAY_SLOT = datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC)  # Sunday


class TestAppointmentService:

    def test_book_appointment_success(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        result = service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=VALID_SLOT,
                type=AppointmentType.CONSULTATION,
            ),
            hospital_id=hospital.id,
            patient_id=patient.id,
            user_id=user.id,
        )

        assert result.id is not None
        assert result.status.value == "scheduled"
        assert result.token_number == 1

    def test_double_booking_same_slot_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient1 = PatientFactory.create(db, hospital.id)
        patient2 = PatientFactory.create(db, hospital.id)
        user1 = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        user2 = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        service.book(
            data=AppointmentCreate(doctor_id=doctor.id, slot_time=VALID_SLOT),
            hospital_id=hospital.id,
            patient_id=patient1.id,
            user_id=user1.id,
        )

        with pytest.raises(ValueError, match="Slot is already booked"):
            service.book(
                data=AppointmentCreate(doctor_id=doctor.id, slot_time=VALID_SLOT),
                hospital_id=hospital.id,
                patient_id=patient2.id,
                user_id=user2.id,
            )

    def test_booking_outside_hours_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        with pytest.raises(ValueError, match="outside doctor's working hours"):
            service.book(
                data=AppointmentCreate(doctor_id=doctor.id, slot_time=OUTSIDE_HOURS_SLOT),
                hospital_id=hospital.id,
                patient_id=patient.id,
                user_id=user.id,
            )

    def test_booking_on_no_schedule_day_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        with pytest.raises(ValueError, match="does not work on Sunday"):
            service.book(
                data=AppointmentCreate(doctor_id=doctor.id, slot_time=SUNDAY_SLOT),
                hospital_id=hospital.id,
                patient_id=patient.id,
                user_id=user.id,
            )

    def test_token_number_increments(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        slots = [
            datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
            datetime(2025, 6, 2, 10, 15, tzinfo=UTC),
            datetime(2025, 6, 2, 10, 30, tzinfo=UTC),
        ]

        for i, slot in enumerate(slots):
            patient = PatientFactory.create(db, hospital.id)
            result = service.book(
                data=AppointmentCreate(doctor_id=doctor.id, slot_time=slot),
                hospital_id=hospital.id,
                patient_id=patient.id,
                user_id=user.id,
            )
            assert result.token_number == i + 1

    def test_cancel_appointment(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        appointment = service.book(
            data=AppointmentCreate(doctor_id=doctor.id, slot_time=VALID_SLOT),
            hospital_id=hospital.id,
            patient_id=patient.id,
            user_id=user.id,
        )

        cancelled = service.cancel(
            appointment_id=appointment.id,
            hospital_id=hospital.id,
            reason="Patient request",
            cancelled_by_user_id=user.id,
        )

        assert cancelled.status.value == "cancelled"

    def test_cancel_already_cancelled_raises(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        service = AppointmentService(db)

        appointment = service.book(
            data=AppointmentCreate(doctor_id=doctor.id, slot_time=VALID_SLOT),
            hospital_id=hospital.id,
            patient_id=patient.id,
            user_id=user.id,
        )
        service.cancel(
            appointment_id=appointment.id,
            hospital_id=hospital.id,
            reason="First cancel",
            cancelled_by_user_id=user.id,
        )

        with pytest.raises(ValueError, match="Cannot cancel"):
            service.cancel(
                appointment_id=appointment.id,
                hospital_id=hospital.id,
                reason="Second cancel",
                cancelled_by_user_id=user.id,
            )
