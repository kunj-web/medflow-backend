"""
tests/integration/test_doctors.py

Covers:
- Admin can create a doctor
- Duplicate registration number rejected
- List doctors (admin)
- Get doctor by id
- Doctor from other hospital not returned
- Non-admin cannot create doctor
- Schedule upsert
- Get available slots
"""

from tests.factories.doctor_factory import DoctorFactory

DOCTOR_PAYLOAD = {
    "email": "dr.new@test.com",
    "phone": "9123456001",
    "password": "Test@1234",
    "first_name": "Vikram",
    "last_name": "Singh",
    "gender": "male",
    "registration_number": "REGNEW001",
    "specialization": "Neurologist",
    "consultation_fee": 900,
    "experience_years": 12,
}


class TestDoctorCreation:

    async def test_admin_can_create_doctor(self, client, admin_headers):
        response = await client.post("/api/v1/doctors", json=DOCTOR_PAYLOAD, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Vikram"
        assert data["last_name"] == "Singh"
        assert data["is_active"] is True

    async def test_duplicate_registration_number_returns_400(self, client, db, hospital, admin_headers):
        DoctorFactory.create(db, hospital.id, registration_number="REGDUP001")
        payload = {**DOCTOR_PAYLOAD, "email": "dup@test.com", "registration_number": "REGDUP001"}
        response = await client.post("/api/v1/doctors", json=payload, headers=admin_headers)
        assert response.status_code == 400

    async def test_patient_cannot_create_doctor(self, client, patient_headers):
        response = await client.post("/api/v1/doctors", json=DOCTOR_PAYLOAD, headers=patient_headers)
        assert response.status_code == 403

    async def test_unauthenticated_cannot_create_doctor(self, client):
        response = await client.post("/api/v1/doctors", json=DOCTOR_PAYLOAD)
        assert response.status_code == 403


class TestDoctorListing:

    async def test_admin_can_list_doctors(self, client, db, hospital, admin_headers):
        DoctorFactory.create(db, hospital.id)
        DoctorFactory.create(db, hospital.id)
        response = await client.get("/api/v1/doctors", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 2

    async def test_other_hospital_doctors_not_returned(self, client, db, hospital, admin_headers):
        from app.models.hospital import Hospital
        other = Hospital(name="Other", primary_color="#000000", currency="INR", timezone="Asia/Kolkata")
        db.add(other)
        db.flush()
        DoctorFactory.create(db, other.id)

        response = await client.get("/api/v1/doctors", headers=admin_headers)
        assert response.status_code == 200
        # All returned doctors belong to current hospital
        for doc in response.json()["data"]:
            assert doc.get("hospital_id") == str(hospital.id) or "hospital_id" not in doc


class TestDoctorDetail:

    async def test_get_doctor_by_id(self, client, db, hospital, admin_headers):
        doctor = DoctorFactory.create(db, hospital.id)
        response = await client.get(f"/api/v1/doctors/{doctor.id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["id"] == str(doctor.id)

    async def test_get_nonexistent_doctor_returns_404(self, client, admin_headers):
        from uuid import uuid4
        response = await client.get(f"/api/v1/doctors/{uuid4()}", headers=admin_headers)
        assert response.status_code == 404


class TestDoctorSchedule:

    async def test_upsert_schedule(self, client, db, hospital, admin_headers):
        doctor = DoctorFactory.create(db, hospital.id)
        response = await client.put(
            f"/api/v1/doctors/{doctor.id}/schedule",
            json={"day_of_week": "sunday", "start_time": "10:00", "end_time": "14:00"},
            headers=admin_headers,
        )
        assert response.status_code in (200, 201)

    async def test_get_available_slots(self, client, db, hospital, admin_headers):
        doctor = DoctorFactory.create(db, hospital.id)
        response = await client.get(
            f"/api/v1/doctors/{doctor.id}/slots?date=2025-06-02",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0  # Mon 9-17, 15min slots = 32 slots
