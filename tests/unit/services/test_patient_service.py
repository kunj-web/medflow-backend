from datetime import date, datetime, time, timedelta

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, AppointmentType, DayOfWeek, UserRole
from app.schemas.pagination import PaginationParams
from app.schemas.patient import PatientUpdate
from app.services.patient_service import PatientService
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


def create_appointment(db, patient, doctor, slot_time=None):
    starts_at = slot_time or datetime.combine(next_weekday(DayOfWeek.MONDAY), time(9, 0))
    appointment = Appointment(
        hospital_id=doctor.hospital_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        slot_time=starts_at,
        end_time=starts_at + timedelta(minutes=15),
        status=AppointmentStatus.SCHEDULED,
        type=AppointmentType.CONSULTATION,
        token_number=1,
    )
    db.add(appointment)
    db.flush()
    return appointment


class TestPatientProfile:
    def test_get_profile_for_user(self, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)

        result = PatientService(db).get_profile_for_user(user.id)

        assert result.id == patient.id

    def test_get_by_id_with_appointments(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)
        doctor = DoctorFactory.create(db, hospital.id)
        create_appointment(db, patient, doctor)

        result = PatientService(db).get_by_id_with_appointments(patient.id)

        assert result.id == patient.id
        assert len(result.appointments) == 1


class TestPatientListing:
    def test_list_all_returns_paginated_patients(self, db, hospital):
        PatientFactory.create(db, hospital.id)
        PatientFactory.create(db, hospital.id)

        result = PatientService(db).list_all(PaginationParams(page=1, page_size=1))

        assert len(result.data) == 1
        assert result.total == 2
        assert result.total_pages == 2

    def test_list_all_searches_by_name(self, db, hospital):
        PatientFactory.create(db, hospital.id, first_name="Ramesh", last_name="Kumar")
        PatientFactory.create(db, hospital.id, first_name="Suresh", last_name="Patel")

        result = PatientService(db).list_all(
            PaginationParams(page=1, page_size=20),
            search="Ramesh",
        )

        assert len(result.data) == 1
        assert result.data[0].first_name == "Ramesh"

    def test_list_all_searches_by_phone(self, db, hospital):
        PatientFactory.create(db, hospital.id, phone="9888888888")

        result = PatientService(db).list_all(
            PaginationParams(page=1, page_size=20),
            search="9888888888",
        )

        assert len(result.data) == 1
        assert result.data[0].phone == "9888888888"


class TestPatientUpdateDelete:
    def test_update_patient_and_linked_user_contact(self, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)

        result = PatientService(db).update(
            patient.id,
            PatientUpdate(
                first_name="Updated",
                phone="9876543210",
                email="updated@test.com",
            ),
        )

        db.refresh(user)
        assert result.first_name == "Updated"
        assert result.phone == "9876543210"
        assert user.phone == "9876543210"
        assert user.email == "updated@test.com"

    def test_delete_soft_deletes_patient(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)

        PatientService(db).delete(patient.id)

        assert PatientService(db).get_profile_for_user(patient.user_id) is None


class TestPatientAccess:
    def test_doctor_has_access_after_appointment(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)
        doctor = DoctorFactory.create(db, hospital.id)
        create_appointment(db, patient, doctor)

        assert PatientService(db).doctor_has_access(patient.id, doctor.user_id) is True

    def test_doctor_without_appointment_has_no_access(self, db, hospital):
        patient = PatientFactory.create(db, hospital.id)
        doctor = DoctorFactory.create(db, hospital.id)

        assert PatientService(db).doctor_has_access(patient.id, doctor.user_id) is False


class TestPatientAppointmentHistory:
    def test_appointment_history_scoped_to_patient(self, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient1 = PatientFactory.create(db, hospital.id)
        patient2 = PatientFactory.create(db, hospital.id)
        create_appointment(
            db,
            patient1,
            doctor,
            datetime.combine(next_weekday(DayOfWeek.MONDAY), time(9, 0)),
        )
        create_appointment(
            db,
            patient2,
            doctor,
            datetime.combine(next_weekday(DayOfWeek.MONDAY), time(9, 15)),
        )

        history = PatientService(db).get_appointment_history(
            patient1.id,
            PaginationParams(page=1, page_size=20),
        )

        assert history.total == 1
        assert history.data[0].patient.id == patient1.id
