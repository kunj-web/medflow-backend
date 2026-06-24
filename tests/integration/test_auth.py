from app.models.doctor import Doctor
from app.models.enums import AccountStatus, UserRole, WorkType
from app.models.user import User


class TestAuthRoutes:

    async def test_register_patient(self, client, db):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "patient@test.com",
                "phone": "9876543210",
                "password": "Test@1234",
                "name": "Test Patient",
                "role": "patient",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "patient"
        assert data["status"] == "active"
        assert data["message"]
        assert "user_id" in data
        assert "access_token" not in data
        assert "refresh_token" not in data

    async def test_register_duplicate_email_fails(self, client):
        payload = {
            "email": "dup@test.com",
            "phone": "9876543211",
            "password": "Test@1234",
            "name": "Test",
            "role": "patient",
        }

        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400

    async def test_register_patient_rejects_doctor_fields(self, client, hospital):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "patient-doctor-fields@test.com",
                "phone": "9876543212",
                "password": "Test@1234",
                "name": "Patient With Hospital",
                "role": "patient",
                "hospital_id": str(hospital.id),
            },
        )

        assert response.status_code == 422

    async def test_register_doctor_with_existing_hospital_is_pending(
        self, client, db, hospital
    ):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "doctor@test.com",
                "phone": "9876543213",
                "password": "Test@1234",
                "name": "Test Doctor",
                "role": "doctor",
                "specialization": "Cardiology",
                "qualification": "MBBS",
                "registration_number": "REG-123",
                "experience_years": 7,
                "work_type": "hospital",
                "gender": "male",
                "hospital_id": str(hospital.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "doctor"
        assert data["status"] == "pending"
        assert "access_token" not in data

        user = db.query(User).filter(User.email == "doctor@test.com").one()
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).one()
        assert user.status == AccountStatus.PENDING
        assert user.role == UserRole.DOCTOR
        assert doctor.work_type == WorkType.HOSPITAL
        assert doctor.hospital_id == hospital.id

    async def test_register_doctor_with_manual_hospital_is_pending(self, client, db):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "manual-doctor@test.com",
                "phone": "9876543214",
                "password": "Test@1234",
                "name": "Manual Doctor",
                "role": "doctor",
                "specialization": "Dermatology",
                "work_type": "hospital",
                "gender": "female",
                "pending_hospital_name": "New City Hospital",
                "pending_hospital_city": "Pune",
                "pending_hospital_state": "Maharashtra",
            },
        )

        assert response.status_code == 201
        user = db.query(User).filter(User.email == "manual-doctor@test.com").one()
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).one()
        assert user.status == AccountStatus.PENDING
        assert doctor.hospital_id is None
        assert doctor.pending_hospital_name == "New City Hospital"

    async def test_register_doctor_with_clinic_is_pending(self, client, db):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "clinic-doctor@test.com",
                "phone": "9876543215",
                "password": "Test@1234",
                "name": "Clinic Doctor",
                "role": "doctor",
                "specialization": "Pediatrics",
                "work_type": "clinic",
                "gender": "other",
                "clinic_name": "Care Clinic",
                "clinic_city": "Mumbai",
            },
        )

        assert response.status_code == 201
        user = db.query(User).filter(User.email == "clinic-doctor@test.com").one()
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).one()
        assert user.status == AccountStatus.PENDING
        assert doctor.work_type == WorkType.CLINIC
        assert doctor.clinic_name == "Care Clinic"
        assert doctor.clinic_city == "Mumbai"

    async def test_login_success(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@test.com",
                "phone": "9876543216",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@test.com",
                "password": "Test@1234",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "patient"
        assert data["status"] == "active"

    async def test_login_pending_doctor_fails(self, client, hospital):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "pending-login@test.com",
                "phone": "9876543217",
                "password": "Test@1234",
                "name": "Pending Doctor",
                "role": "doctor",
                "specialization": "Neurology",
                "work_type": "hospital",
                "gender": "male",
                "hospital_id": str(hospital.id),
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "pending-login@test.com",
                "password": "Test@1234",
            },
        )

        assert response.status_code == 401

    async def test_login_wrong_password(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong@test.com",
                "phone": "9876543218",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@test.com",
                "password": "WrongPassword",
            },
        )

        assert response.status_code == 401

    async def test_refresh_token(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@test.com",
                "phone": "9876543219",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
            },
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "refresh@test.com",
                "password": "Test@1234",
            },
        )
        refresh_token = login.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_invalid_token_returns_401(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )

        assert response.status_code == 401
