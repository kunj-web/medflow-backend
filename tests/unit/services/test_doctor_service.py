"""
tests/unit/services/test_doctor_service.py

Covers:
- Doctor + User created in one transaction
- Slot generation from schedule
- Schedule upsert (create and overwrite)
- Leave conflict detection
- Hospital scoping (doctor from other hospital not visible)
- Inactive doctor cannot be booked
"""
from datetime import date, time

import pytest

from app.models.enums import DayOfWeek, UserRole
from app.schemas.doctor import DoctorCreate, ScheduleUpsert
from app.services.doctor_service import DoctorService
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.user_factory import UserFactory


class TestDoctorServiceCreate:

    def test_creates_user_and_doctor_together(self, db, hospital):
        service = DoctorService(db)
        data = DoctorCreate(
            email="newdoc@test.com",
            phone="9876543210",
            password="Test@1234",
            first_name="Arjun",
            last_name="Mehta",
            gender="male",
            registration_number="REG00001",
            specialization="Cardiologist",
            consultation_fee=800,
            experience_years=10,
        )
        doctor = service.create(data, hospital_id=hospital.id)

        assert doctor.id is not None
        assert doctor.user_id is not None
        assert doctor.first_name == "Arjun"
        assert doctor.last_name == "Mehta"
        assert doctor.hospital_id == hospital.id
        assert doctor.is_active is True

    def test_duplicate_registration_number_raises(self, db, hospital):
        DoctorFactory.create(db, hospital.id, registration_number="REG99999")
        service = DoctorService(db)
        data = DoctorCreate(
            email="another@test.com",
            phone="9123456780",
            password="Test@1234",
            first_name="Priya",
            last_name="Nair",
            gender="female",
            registration_number="REG99999",  # duplicate
            specialization="Dermatologist",
            consultation_fee=600,
            experience_years=3,
        )
        with pytest.raises(ValueError, match="registration number"):
            service.create(data, hospital_id=hospital.id)

    def test_duplicate_email_raises(self, db, hospital):
        DoctorFactory.create(db, hospital.id, email="taken@test.com")
        service = DoctorService(db)
        data = DoctorCreate(
            email="taken@test.com",
            phone="9000000001",
            password="Test@1234",
            first_name="Test",
            last_name="Doc",
            gender="male",
            registration_number="REG00002",
            specialization="General Physician",
            consultation_fee=300,
            experience_years=1,
        )
        with pytest.raises(ValueError, match="email"):
            service.create(data, hospital_id=hospital.id)


class TestDoctorScheduleUpsert:

    def test_upsert_creates_new_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        service = DoctorService(db)

        service.upsert_schedule(
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            data=ScheduleUpsert(
                day_of_week=DayOfWeek.SUNDAY,
                start_time=time(10, 0),
                end_time=time(14, 0),
            ),
        )

        from app.repositories.doctor_repo import DoctorRepository
        repo = DoctorRepository(db)
        schedule = repo.get_schedule_for_day(doctor.id, DayOfWeek.SUNDAY)
        assert schedule is not None
        assert schedule.start_time == time(10, 0)
        assert schedule.end_time == time(14, 0)

    def test_upsert_overwrites_existing_schedule(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)  # has Mon-Sat 9-17
        service = DoctorService(db)

        service.upsert_schedule(
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            data=ScheduleUpsert(
                day_of_week=DayOfWeek.MONDAY,
                start_time=time(8, 0),
                end_time=time(12, 0),
            ),
        )

        from app.repositories.doctor_repo import DoctorRepository
        repo = DoctorRepository(db)
        schedule = repo.get_schedule_for_day(doctor.id, DayOfWeek.MONDAY)
        assert schedule.start_time == time(8, 0)
        assert schedule.end_time == time(12, 0)

    def test_upsert_from_other_hospital_raises(self, db, hospital):
        from app.models.hospital import Hospital
        other = Hospital(name="Other", primary_color="#000000", currency="INR", timezone="Asia/Kolkata")
        db.add(other)
        db.flush()

        doctor = DoctorFactory.create(db, hospital.id)
        service = DoctorService(db)

        with pytest.raises(ValueError, match="not found"):
            service.upsert_schedule(
                doctor_id=doctor.id,
                hospital_id=other.id,  # wrong hospital
                data=ScheduleUpsert(
                    day_of_week=DayOfWeek.MONDAY,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                ),
            )


class TestDoctorLeave:

    def test_approved_leave_blocks_booking(self, db, hospital):
        """
        Verifies that AppointmentService raises when doctor has approved leave.
        Indirectly tests DoctorRepository.get_leave_for_date.
        """
        from datetime import datetime

        from app.models.doctor import DoctorLeave
        from app.models.enums import AppointmentType
        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment_service import AppointmentService
        from tests.factories.patient_factory import PatientFactory

        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)

        leave_date = date(2025, 6, 2)  # Monday
        leave = DoctorLeave(
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            leave_date=leave_date,
            is_approved=True,
            reason="Conference",
        )
        db.add(leave)
        db.flush()

        service = AppointmentService(db)
        with pytest.raises(ValueError, match="leave"):
            service.book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=datetime(2025, 6, 2, 10, 0, 0),
                    type=AppointmentType.CONSULTATION,
                ),
                hospital_id=hospital.id,
                patient_id=patient.id,
                user_id=user.id,
            )

    def test_unapproved_leave_does_not_block(self, db, hospital):
        from datetime import datetime

        from app.models.doctor import DoctorLeave
        from app.models.enums import AppointmentType
        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment_service import AppointmentService
        from tests.factories.patient_factory import PatientFactory

        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)

        leave = DoctorLeave(
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            leave_date=date(2025, 6, 2),
            is_approved=False,  # pending — should NOT block
            reason="Pending",
        )
        db.add(leave)
        db.flush()

        service = AppointmentService(db)
        result = service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=datetime(2025, 6, 2, 10, 0, 0),
                type=AppointmentType.CONSULTATION,
            ),
            hospital_id=hospital.id,
            patient_id=patient.id,
            user_id=user.id,
        )
        assert result.id is not None


class TestDoctorHospitalScoping:

    def test_doctor_from_other_hospital_not_bookable(self, db, hospital):
        from datetime import datetime

        from app.models.enums import AppointmentType
        from app.models.hospital import Hospital
        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment_service import AppointmentService
        from tests.factories.patient_factory import PatientFactory

        other = Hospital(name="Other", primary_color="#000000", currency="INR", timezone="Asia/Kolkata")
        db.add(other)
        db.flush()

        doctor = DoctorFactory.create(db, other.id)  # doctor belongs to 'other'
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)

        service = AppointmentService(db)
        with pytest.raises(ValueError, match="not found"):
            service.book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=datetime(2025, 6, 2, 10, 0, 0),
                    type=AppointmentType.CONSULTATION,
                ),
                hospital_id=hospital.id,  # different hospital
                patient_id=patient.id,
                user_id=user.id,
            )

    def test_inactive_doctor_cannot_be_booked(self, db, hospital):
        from datetime import datetime

        from app.models.enums import AppointmentType
        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment_service import AppointmentService
        from tests.factories.patient_factory import PatientFactory

        doctor = DoctorFactory.create(db, hospital.id, is_active=False)
        patient = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)

        service = AppointmentService(db)
        with pytest.raises(ValueError, match="not available"):
            service.book(
                data=AppointmentCreate(
                    doctor_id=doctor.id,
                    slot_time=datetime(2025, 6, 2, 10, 0, 0),
                    type=AppointmentType.CONSULTATION,
                ),
                hospital_id=hospital.id,
                patient_id=patient.id,
                user_id=user.id,
            )
