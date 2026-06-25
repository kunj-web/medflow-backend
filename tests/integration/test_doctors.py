from datetime import date, timedelta
from uuid import uuid4

from app.core.security import create_token_pair
from app.models.enums import AccountStatus, DayOfWeek, UserRole
from tests.factories.doctor_factory import DoctorFactory
from tests.factories.user_factory import UserFactory


def next_weekday(day: DayOfWeek) -> date:
    target = list(DayOfWeek).index(day)
    today = date.today()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def headers_for(user_id, role=UserRole.DOCTOR):
    tokens = create_token_pair(
        str(user_id),
        role.value,
        AccountStatus.ACTIVE.value,
        role == UserRole.WEBSITE_ADMIN,
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


class TestDoctorListing:
    async def test_public_list_returns_active_approved_doctors(self, client, db, hospital):
        active = DoctorFactory.create(db, hospital.id, specialization="Cardiologist")
        inactive = DoctorFactory.create(db, hospital.id, is_active=False)
        pending_user = UserFactory.create(
            db,
            hospital.id,
            role=UserRole.DOCTOR,
            status=AccountStatus.PENDING,
        )
        pending = DoctorFactory.create(db, hospital.id, user_id=pending_user.id)

        response = await client.get("/api/v1/doctors")

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["data"]}
        assert str(active.id) in ids
        assert str(inactive.id) not in ids
        assert str(pending.id) not in ids

    async def test_public_list_can_filter_by_hospital(self, client, db, hospital):
        from app.models.hospital import Hospital

        first = DoctorFactory.create(db, hospital.id)
        other_hospital = Hospital(
            name="Other Hospital",
            primary_color="#000000",
            currency="INR",
            timezone="Asia/Kolkata",
        )
        db.add(other_hospital)
        db.flush()
        other = DoctorFactory.create(db, other_hospital.id)

        response = await client.get(f"/api/v1/doctors?hospital_id={hospital.id}")

        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["data"]}
        assert str(first.id) in ids
        assert str(other.id) not in ids


class TestDoctorDetail:
    async def test_get_doctor_by_id(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)

        response = await client.get(f"/api/v1/doctors/{doctor.id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(doctor.id)

    async def test_pending_doctor_is_not_public(self, client, db, hospital):
        pending_user = UserFactory.create(
            db,
            hospital.id,
            role=UserRole.DOCTOR,
            status=AccountStatus.PENDING,
        )
        doctor = DoctorFactory.create(db, hospital.id, user_id=pending_user.id)

        response = await client.get(f"/api/v1/doctors/{doctor.id}")

        assert response.status_code == 404

    async def test_get_nonexistent_doctor_returns_404(self, client):
        response = await client.get(f"/api/v1/doctors/{uuid4()}")

        assert response.status_code == 404


class TestDoctorSchedule:
    async def test_admin_can_set_schedule(self, client, db, hospital, admin_headers):
        doctor = DoctorFactory.create(db, hospital.id)

        response = await client.post(
            f"/api/v1/doctors/{doctor.id}/schedule",
            json={
                "day_of_week": "sunday",
                "start_time": "10:00",
                "end_time": "14:00",
            },
            headers=admin_headers,
        )

        assert response.status_code == 201
        assert response.json()["day_of_week"] == "sunday"

    async def test_owner_doctor_can_set_schedule(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)

        response = await client.post(
            f"/api/v1/doctors/{doctor.id}/schedule",
            json={
                "day_of_week": "sunday",
                "start_time": "10:00",
                "end_time": "14:00",
            },
            headers=headers_for(doctor.user_id),
        )

        assert response.status_code == 201

    async def test_other_doctor_cannot_set_schedule(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        other = DoctorFactory.create(db, hospital.id)

        response = await client.post(
            f"/api/v1/doctors/{doctor.id}/schedule",
            json={
                "day_of_week": "sunday",
                "start_time": "10:00",
                "end_time": "14:00",
            },
            headers=headers_for(other.user_id),
        )

        assert response.status_code == 403

    async def test_get_available_slots(self, client, db, hospital):
        doctor = DoctorFactory.create(db, hospital.id)
        target = next_weekday(DayOfWeek.MONDAY)

        response = await client.get(
            f"/api/v1/doctors/{doctor.id}/slots?date={target.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 32
