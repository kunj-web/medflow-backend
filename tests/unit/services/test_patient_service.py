"""
tests/unit/services/test_patient_service.py

Covers:
- Patient + User created in one transaction
- Duplicate phone/email raises
- Search by name, phone
- Appointment history scoped to patient
- Hospital scoping
"""
import pytest

from app.models.enums import UserRole
from app.services.patient_service import PatientService
from app.schemas.patient import PatientCreate
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory
from tests.factories.user_factory import UserFactory


class TestPatientServiceCreate:

    def test_creates_user_and_patient_together(self, db, hospital):
        service = PatientService(db)
        data = PatientCreate(
            email="patient1@test.com",
            phone="9000000001",
            password="Test@1234",
            first_name="Sneha",
            last_name="Rao",
            gender="female",
        )
        patient = service.create(data, hospital_id=hospital.id)

        assert patient.id is not None
        assert patient.user_id is not None
        assert patient.first_name == "Sneha"
        assert patient.last_name == "Rao"
        assert patient.hospital_id == hospital.id

    def test_duplicate_email_raises(self, db, hospital):
        PatientFactory.create(db, hospital.id, email="taken@test.com")
        service = PatientService(db)
        data = PatientCreate(
            email="taken@test.com",
            phone="9000000002",
            password="Test@1234",
            first_name="Another",
            last_name="Person",
            gender="male",
        )
        with pytest.raises(ValueError, match="email"):
            service.create(data, hospital_id=hospital.id)

    def test_duplicate_phone_raises(self, db, hospital):
        PatientFactory.create(db, hospital.id, phone="9111111111")
        service = PatientService(db)
        data = PatientCreate(
            email="unique@test.com",
            phone="9111111111",  # duplicate
            password="Test@1234",
            first_name="Test",
            last_name="User",
            gender="male",
        )
        with pytest.raises(ValueError, match="phone"):
            service.create(data, hospital_id=hospital.id)


class TestPatientSearch:

    def test_search_by_first_name(self, db, hospital):
        PatientFactory.create(db, hospital.id, first_name="Ramesh", last_name="Kumar")
        PatientFactory.create(db, hospital.id, first_name="Suresh", last_name="Patel")
        service = PatientService(db)

        results = service.search(query="Ramesh", hospital_id=hospital.id)
        assert len(results) >= 1
        assert any(p.first_name == "Ramesh" for p in results)

    def test_search_by_phone(self, db, hospital):
        PatientFactory.create(db, hospital.id, phone="9888888888")
        service = PatientService(db)

        results = service.search(query="9888888888", hospital_id=hospital.id)
        assert len(results) >= 1
        assert any(p.phone == "9888888888" for p in results)

    def test_search_returns_only_own_hospital(self, db, hospital):
        from app.models.hospital import Hospital
        other = Hospital(name="Other", primary_color="#000000", currency="INR", timezone="Asia/Kolkata")
        db.add(other)
        db.flush()

        PatientFactory.create(db, other.id, first_name="Ghost", last_name="Patient")
        PatientFactory.create(db, hospital.id, first_name="Real", last_name="Patient")
        service = PatientService(db)

        results = service.search(query="Patient", hospital_id=hospital.id)
        assert all(p.hospital_id == hospital.id for p in results)
        assert not any(p.first_name == "Ghost" for p in results)

    def test_search_empty_query_returns_all(self, db, hospital):
        PatientFactory.create(db, hospital.id)
        PatientFactory.create(db, hospital.id)
        service = PatientService(db)

        results = service.search(query="", hospital_id=hospital.id)
        assert len(results) >= 2


class TestPatientAppointmentHistory:

    def test_appointment_history_scoped_to_patient(self, db, hospital):
        from datetime import datetime
        from app.models.enums import AppointmentType
        from app.schemas.appointment import AppointmentCreate
        from app.services.appointment_service import AppointmentService

        doctor = DoctorFactory.create(db, hospital.id)
        patient1 = PatientFactory.create(db, hospital.id)
        patient2 = PatientFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)

        apt_service = AppointmentService(db)
        apt_service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=datetime(2025, 6, 2, 9, 0, 0),
                type=AppointmentType.CONSULTATION,
            ),
            hospital_id=hospital.id,
            patient_id=patient1.id,
            user_id=user.id,
        )
        apt_service.book(
            data=AppointmentCreate(
                doctor_id=doctor.id,
                slot_time=datetime(2025, 6, 2, 9, 15, 0),
                type=AppointmentType.CONSULTATION,
            ),
            hospital_id=hospital.id,
            patient_id=patient2.id,
            user_id=user.id,
        )

        service = PatientService(db)
        history = service.get_appointment_history(
            patient_id=patient1.id,
            hospital_id=hospital.id,
        )
        assert all(a.patient_id == patient1.id for a in history)
        assert len(history) == 1