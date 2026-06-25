from app.models.doctor import Doctor
from app.models.enums import AccountStatus
from app.models.hospital import Hospital
from app.models.user import User


async def register_hospital_doctor(client, hospital, email="review-doctor@test.com"):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone": "9876500001",
            "password": "Test@1234",
            "name": "Review Doctor",
            "role": "doctor",
            "specialization": "Cardiology",
            "work_type": "hospital",
            "gender": "male",
            "hospital_id": str(hospital.id),
        },
    )
    assert response.status_code == 201
    return response.json()


async def register_manual_hospital_doctor(client, email="manual-review@test.com"):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone": "9876500002",
            "password": "Test@1234",
            "name": "Manual Review",
            "role": "doctor",
            "specialization": "Dermatology",
            "work_type": "hospital",
            "gender": "female",
            "pending_hospital_name": "Review City Hospital",
            "pending_hospital_city": "Delhi",
            "pending_hospital_state": "Delhi",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestAdminDoctorReview:

    async def test_list_pending_doctors_requires_admin(self, client, hospital):
        await register_hospital_doctor(client, hospital, email="requires-admin@test.com")

        response = await client.get("/api/v1/admin/doctors/pending")

        assert response.status_code == 401

    async def test_list_pending_doctors(self, client, hospital, admin_headers):
        await register_hospital_doctor(client, hospital, email="pending-list@test.com")

        response = await client.get(
            "/api/v1/admin/doctors/pending",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"
        assert data[0]["work_type"] == "hospital"
        assert data[0]["hospital_id"] == str(hospital.id)

    async def test_approve_existing_hospital_doctor_allows_login(
        self, client, db, hospital, admin_headers
    ):
        await register_hospital_doctor(client, hospital, email="approve-existing@test.com")
        doctor = (
            db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.email == "approve-existing@test.com")
            .one()
        )

        response = await client.post(
            f"/api/v1/admin/doctors/{doctor.id}/approve",
            json={},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

        db.expire_all()
        user = db.query(User).filter(User.email == "approve-existing@test.com").one()
        assert user.status == AccountStatus.ACTIVE
        assert user.is_verified is True

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "approve-existing@test.com",
                "password": "Test@1234",
            },
        )
        assert login.status_code == 200
        assert login.json()["role"] == "doctor"

    async def test_approve_manual_hospital_doctor_creates_hospital(
        self, client, db, admin_headers
    ):
        await register_manual_hospital_doctor(client, email="approve-manual@test.com")
        doctor = (
            db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.email == "approve-manual@test.com")
            .one()
        )

        response = await client.post(
            f"/api/v1/admin/doctors/{doctor.id}/approve",
            json={
                "create_hospital": {
                    "name": "Review City Hospital",
                    "city": "Delhi",
                    "state": "Delhi",
                }
            },
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["hospital_id"] is not None
        assert data["pending_hospital_name"] is None

        db.expire_all()
        hospital = db.query(Hospital).filter(Hospital.name == "Review City Hospital").one()
        doctor = db.query(Doctor).filter(Doctor.id == doctor.id).one()
        assert doctor.hospital_id == hospital.id
        assert doctor.pending_hospital_name is None

    async def test_reject_pending_doctor_blocks_login(self, client, db, hospital, admin_headers):
        await register_hospital_doctor(client, hospital, email="reject-review@test.com")
        doctor = (
            db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(User.email == "reject-review@test.com")
            .one()
        )

        response = await client.post(
            f"/api/v1/admin/doctors/{doctor.id}/reject",
            json={"reason": "Registration details could not be verified"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "reject-review@test.com",
                "password": "Test@1234",
            },
        )
        assert login.status_code == 401
