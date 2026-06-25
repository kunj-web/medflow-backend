from datetime import date, datetime, time, timedelta
from uuid import uuid4

from app.core.security import create_token_pair
from app.models.enums import AccountStatus, DayOfWeek, UserRole
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


def headers_for(user_id, role=UserRole.PATIENT):
    tokens = create_token_pair(
        str(user_id),
        role.value,
        AccountStatus.ACTIVE.value,
        role == UserRole.WEBSITE_ADMIN,
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestPatientListing:
    async def test_admin_can_list_patients(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id)
        PatientFactory.create(db, hospital.id)

        response = await client.get("/api/v1/patients", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] == 2

    async def test_patient_cannot_list_all_patients(self, client, patient_headers):
        response = await client.get("/api/v1/patients", headers=patient_headers)

        assert response.status_code == 403

    async def test_pagination_params_respected(self, client, db, hospital, admin_headers):
        for _ in range(5):
            PatientFactory.create(db, hospital.id)

        response = await client.get(
            "/api/v1/patients?page=1&page_size=2",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert len(response.json()["data"]) == 2


class TestPatientSearch:
    async def test_search_by_name(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, first_name="Rajesh", last_name="Gupta")
        PatientFactory.create(db, hospital.id, first_name="Asha", last_name="Patel")

        response = await client.get(
            "/api/v1/patients?search=Rajesh",
            headers=admin_headers,
        )

        assert response.status_code == 200
        results = response.json()["data"]
        assert len(results) == 1
        assert results[0]["first_name"] == "Rajesh"

    async def test_search_by_phone(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, phone="9777777777")

        response = await client.get(
            "/api/v1/patients?search=9777777777",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["data"][0]["phone"] == "9777777777"


class TestPatientDetail:
    async def test_admin_can_get_patient_by_id(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)

        response = await client.get(
            f"/api/v1/patients/{patient.id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(patient.id)

    async def test_get_nonexistent_patient_returns_404(self, client, admin_headers):
        response = await client.get(
            f"/api/v1/patients/{uuid4()}",
            headers=admin_headers,
        )

        assert response.status_code == 404

    async def test_patient_can_get_own_profile(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)

        response = await client.get(
            f"/api/v1/patients/{patient.id}",
            headers=headers_for(user.id),
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(patient.id)

    async def test_patient_cannot_get_other_patient_profile(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        PatientFactory.create(db, hospital.id, user_id=user.id)
        other_patient = PatientFactory.create(db, hospital.id)

        response = await client.get(
            f"/api/v1/patients/{other_patient.id}",
            headers=headers_for(user.id),
        )

        assert response.status_code == 404


class TestPatientUpdate:
    async def test_patient_can_update_own_profile(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)

        response = await client.put(
            f"/api/v1/patients/{patient.id}",
            json={"first_name": "Updated", "phone": "9876543210"},
            headers=headers_for(user.id),
        )

        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"
        assert response.json()["phone"] == "9876543210"

    async def test_patient_cannot_update_other_patient(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        PatientFactory.create(db, hospital.id, user_id=user.id)
        other_patient = PatientFactory.create(db, hospital.id)

        response = await client.put(
            f"/api/v1/patients/{other_patient.id}",
            json={"first_name": "Nope"},
            headers=headers_for(user.id),
        )

        assert response.status_code == 404


class TestPatientAppointmentHistory:
    async def test_patient_appointment_history(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)
        doctor = DoctorFactory.create(db, hospital.id)
        slot_time = datetime.combine(next_weekday(DayOfWeek.MONDAY), time(9, 0))

        booking = await client.post(
            "/api/v1/appointments/",
            json={"doctor_id": str(doctor.id), "slot_time": slot_time.isoformat()},
            headers=headers_for(user.id),
        )
        assert booking.status_code == 201

        response = await client.get(
            f"/api/v1/patients/{patient.id}/appointments",
            headers=headers_for(user.id),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["patient"]["id"] == str(patient.id)
