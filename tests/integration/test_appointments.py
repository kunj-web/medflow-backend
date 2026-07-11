from datetime import date, datetime, time, timedelta
from uuid import UUID

from app.core.security import create_token_pair
from app.models.appointment import Appointment
from app.models.enums import AccountStatus, AppointmentStatus, DayOfWeek, UserRole
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


def headers_for(user_id, role=UserRole.PATIENT):
    tokens = create_token_pair(
        str(user_id),
        role.value,
        AccountStatus.ACTIVE.value,
        role == UserRole.WEBSITE_ADMIN,
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def book(client, doctor, patient):
    return await client.post(
        "/api/v1/appointments/",
        json={
            "doctor_id": str(doctor.id),
            "slot_time": slot_at(DayOfWeek.MONDAY, 10).isoformat(),
        },
        headers=headers_for(patient.user_id),
    )


class TestAppointmentBooking:
    async def test_patient_can_book_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)

        response = await book(client, doctor, patient)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["token_number"] == 1
        assert data["patient"]["id"] == str(patient.id)
        assert data["doctor"]["id"] == str(doctor.id)

    async def test_unauthenticated_cannot_book(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)

        response = await client.post(
            "/api/v1/appointments/",
            json={
                "doctor_id": str(doctor.id),
                "slot_time": slot_at(DayOfWeek.MONDAY, 10).isoformat(),
            },
        )

        assert response.status_code == 401

    async def test_doctor_cannot_book_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)

        response = await client.post(
            "/api/v1/appointments/",
            json={
                "doctor_id": str(doctor.id),
                "slot_time": slot_at(DayOfWeek.MONDAY, 10).isoformat(),
            },
            headers=headers_for(doctor.user_id, UserRole.DOCTOR),
        )

        assert response.status_code == 403


class TestAppointmentListing:
    async def test_admin_can_list_appointments(self, client, db, hospital, admin_headers):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        await book(client, doctor, patient)

        response = await client.get(
            "/api/v1/appointments/?page=1&page_size=20",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["data"]) == 1

    async def test_patient_lists_only_own_appointments(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        other_patient = PatientFactory.create(db, hospital.id)
        await book(client, doctor, patient)

        response = await client.get(
            "/api/v1/appointments/",
            headers=headers_for(other_patient.user_id),
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_doctor_lists_only_own_appointments(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        other_doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        await book(client, doctor, patient)

        response = await client.get(
            "/api/v1/appointments/",
            headers=headers_for(other_doctor.user_id, UserRole.DOCTOR),
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_status_filter_is_applied(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]
        appointment = db.get(Appointment, UUID(appointment_id))
        appointment.status = AppointmentStatus.COMPLETED
        db.commit()

        scheduled = await client.get(
            "/api/v1/appointments/?status=scheduled",
            headers=headers_for(patient.user_id),
        )
        completed = await client.get(
            "/api/v1/appointments/?status=completed",
            headers=headers_for(patient.user_id),
        )

        assert scheduled.status_code == 200
        assert scheduled.json()["total"] == 0
        assert completed.status_code == 200
        assert completed.json()["total"] == 1


class TestAppointmentDetail:
    async def test_patient_can_get_own_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.get(
            f"/api/v1/appointments/{appointment_id}",
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 200
        assert response.json()["id"] == appointment_id

    async def test_other_patient_cannot_get_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        other_patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.get(
            f"/api/v1/appointments/{appointment_id}",
            headers=headers_for(other_patient.user_id),
        )

        assert response.status_code == 404


class TestAppointmentMutations:
    async def test_cancel_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json={"reason": "Patient requested cancellation"},
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_patient_cannot_cancel_on_appointment_day(
        self, client, db, hospital
    ):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]
        appointment = db.get(Appointment, UUID(appointment_id))
        appointment.slot_time = datetime.combine(date.today(), time(10, 0))
        db.commit()

        response = await client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json={"reason": "Same-day cancellation request"},
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 400
        assert "at least one day in advance" in response.json()["detail"]

    async def test_doctor_can_cancel_own_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json={"reason": "Doctor unavailable"},
            headers=headers_for(doctor.user_id, UserRole.DOCTOR),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_other_doctor_cannot_cancel_appointment(
        self, client, db, hospital
    ):
        doctor = DoctorFactory.create(db, hospital.id)
        other_doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json={"reason": "Wrong doctor"},
            headers=headers_for(other_doctor.user_id, UserRole.DOCTOR),
        )

        assert response.status_code == 403

    async def test_reschedule_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        patient = PatientFactory.create(db, hospital.id)
        appointment_id = (await book(client, doctor, patient)).json()["id"]

        response = await client.post(
            f"/api/v1/appointments/{appointment_id}/reschedule",
            json={"new_slot_time": slot_at(DayOfWeek.MONDAY, 11).isoformat()},
            headers=headers_for(patient.user_id),
        )

        assert response.status_code == 200
        assert response.json()["slot_time"].startswith(
            slot_at(DayOfWeek.MONDAY, 11).isoformat()
        )


class TestAppointmentQueue:
    async def test_get_today_queue_as_admin(self, client, admin_headers):
        response = await client.get(
            "/api/v1/appointments/queue/today",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert "data" in response.json()
