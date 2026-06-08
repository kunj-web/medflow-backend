"""
tests/integration/test_patients.py

Covers:
- Admin/staff can create patient
- Duplicate email/phone rejected
- List patients with pagination
- Search patients
- Get patient by id
- Patient cannot access other patients
- Get patient's own appointment history
"""
import pytest

from tests.factories.patient_factory import PatientFactory
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.user_factory import UserFactory
from app.core.security import create_token_pair
from app.models.enums import UserRole


PATIENT_PAYLOAD = {
    "email": "newpatient@test.com",
    "phone": "9500000001",
    "password": "Test@1234",
    "first_name": "Ananya",
    "last_name": "Sharma",
    "gender": "female",
}


class TestPatientCreation:

    async def test_admin_can_create_patient(self, client, admin_headers):
        response = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Ananya"
        assert data["last_name"] == "Sharma"

    async def test_duplicate_email_returns_400(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, email="dup@test.com")
        payload = {**PATIENT_PAYLOAD, "email": "dup@test.com", "phone": "9500000099"}
        response = await client.post("/api/v1/patients", json=payload, headers=admin_headers)
        assert response.status_code == 400

    async def test_duplicate_phone_returns_400(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, phone="9500000002")
        payload = {**PATIENT_PAYLOAD, "email": "unique2@test.com", "phone": "9500000002"}
        response = await client.post("/api/v1/patients", json=payload, headers=admin_headers)
        assert response.status_code == 400

    async def test_unauthenticated_cannot_create_patient(self, client):
        response = await client.post("/api/v1/patients", json=PATIENT_PAYLOAD)
        assert response.status_code == 403


class TestPatientListing:

    async def test_admin_can_list_patients(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id)
        PatientFactory.create(db, hospital.id)
        response = await client.get("/api/v1/patients", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data

    async def test_patient_cannot_list_all_patients(self, client, patient_headers):
        response = await client.get("/api/v1/patients", headers=patient_headers)
        assert response.status_code == 403

    async def test_pagination_params_respected(self, client, db, hospital, admin_headers):
        for _ in range(5):
            PatientFactory.create(db, hospital.id)
        response = await client.get("/api/v1/patients?page=1&page_size=2", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()["data"]) <= 2


class TestPatientSearch:

    async def test_search_by_name(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, first_name="Rajesh", last_name="Gupta")
        response = await client.get("/api/v1/patients?search=Rajesh", headers=admin_headers)
        assert response.status_code == 200
        results = response.json()["data"]
        assert any(p["first_name"] == "Rajesh" for p in results)

    async def test_search_by_phone(self, client, db, hospital, admin_headers):
        PatientFactory.create(db, hospital.id, phone="9777777777")
        response = await client.get("/api/v1/patients?search=9777777777", headers=admin_headers)
        assert response.status_code == 200
        results = response.json()["data"]
        assert any(p["phone"] == "9777777777" for p in results)


class TestPatientDetail:

    async def test_admin_can_get_patient_by_id(self, client, db, hospital, admin_headers):
        patient = PatientFactory.create(db, hospital.id)
        response = await client.get(f"/api/v1/patients/{patient.id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["id"] == str(patient.id)

    async def test_get_nonexistent_patient_returns_404(self, client, admin_headers):
        from uuid import uuid4
        response = await client.get(f"/api/v1/patients/{uuid4()}", headers=admin_headers)
        assert response.status_code == 404

    async def test_patient_can_get_own_profile(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)
        tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        response = await client.get(f"/api/v1/patients/{patient.id}", headers=headers)
        assert response.status_code == 200

    async def test_patient_cannot_get_other_patient_profile(self, client, db, hospital):
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        other_patient = PatientFactory.create(db, hospital.id)
        tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        response = await client.get(f"/api/v1/patients/{other_patient.id}", headers=headers)
        assert response.status_code in (403, 404)


class TestPatientAppointmentHistory:

    async def test_patient_appointment_history(self, client, db, hospital):
        from datetime import datetime
        user = UserFactory.create(db, hospital.id, role=UserRole.PATIENT)
        patient = PatientFactory.create(db, hospital.id, user_id=user.id)
        doctor = DoctorFactory.create(db, hospital.id)
        tokens = create_token_pair(str(user.id), "patient", str(hospital.id))
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Book an appointment first
        await client.post(
            "/api/v1/appointments",
            json={"doctor_id": str(doctor.id), "slot_time": "2026-12-07T09:00:00+00:00"},
            headers=headers,
        )

        response = await client.get(
            f"/api/v1/patients/{patient.id}/appointments",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        appointments = data.get("data", data)  # handle both paginated and list
        assert len(appointments) >= 1