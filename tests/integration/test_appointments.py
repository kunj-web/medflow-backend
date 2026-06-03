import pytest
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.patient_factory import PatientFactory
from tests.factories.user_factory import UserFactory
from app.models.enums import UserRole
from app.core.security import create_token_pair

VALID_SLOT = "2026-12-07T10:00:00+00:00"  # future Monday, 15-min aligned


class TestAppointmentRoutes:

    async def test_patient_can_book_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        PatientFactory.create(db, hospital.id, user_id=user.id)
        tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        response = await client.post(
            "/api/v1/appointments",
            json={"doctor_id": str(doctor.id), "slot_time": VALID_SLOT},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["token_number"] == 1

    async def test_unauthenticated_cannot_book(self, client):
        response = await client.post("/api/v1/appointments", json={})
        assert response.status_code == 403

    async def test_doctor_cannot_book_appointment(self, client, doctor_headers):
        response = await client.post(
            "/api/v1/appointments",
            json={"doctor_id": "some-id", "slot_time": VALID_SLOT},
            headers=doctor_headers,
        )
        assert response.status_code == 403

    async def test_admin_can_list_appointments(self, client, admin_headers):
        response = await client.get(
            "/api/v1/appointments?page=1&page_size=20",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "total_pages" in data
        assert "page" in data

    async def test_patient_cannot_list_all_appointments(self, client, patient_headers):
        response = await client.get(
            "/api/v1/appointments",
            headers=patient_headers,
        )
        assert response.status_code == 403

    async def test_cancel_appointment(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        PatientFactory.create(db, hospital.id, user_id=user.id)
        tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        book_res = await client.post(
            "/api/v1/appointments",
            json={"doctor_id": str(doctor.id), "slot_time": VALID_SLOT},
            headers=headers,
        )
        appointment_id = book_res.json()["id"]

        cancel_res = await client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json={"reason": "Patient requested cancellation"},
            headers=headers,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

    async def test_get_today_queue_as_staff(self, client, admin_headers):
        response = await client.get(
            "/api/v1/appointments/queue/today",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert "data" in response.json()

    async def test_auth_me_returns_user_info(self, client, admin_headers):
        response = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert data["role"] == "admin"