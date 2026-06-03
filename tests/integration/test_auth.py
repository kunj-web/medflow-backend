import pytest


class TestAuthRoutes:

    async def test_register_patient(self, client, db, hospital):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "patient@test.com",
                "phone": "9876543210",
                "password": "Test@1234",
                "name": "Test Patient",
                "role": "patient",
                "hospital_id": str(hospital.id),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email_fails(self, client, db, hospital):
        payload = {
            "email": "dup@test.com",
            "phone": "9876543210",
            "password": "Test@1234",
            "name": "Test",
            "role": "patient",
            "hospital_id": str(hospital.id),
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400

    async def test_login_success(self, client, db, hospital):
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@test.com",
                "phone": "9876543210",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
                "hospital_id": str(hospital.id),
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@test.com",
                "password": "Test@1234",
                "hospital_id": str(hospital.id),
            },
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_wrong_password(self, client, db, hospital):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong@test.com",
                "phone": "9876543210",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
                "hospital_id": str(hospital.id),
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@test.com",
                "password": "WrongPassword",
                "hospital_id": str(hospital.id),
            },
        )
        assert response.status_code == 401

    async def test_refresh_token(self, client, db, hospital):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@test.com",
                "phone": "9876543210",
                "password": "Test@1234",
                "name": "Test",
                "role": "patient",
                "hospital_id": str(hospital.id),
            },
        )
        refresh_token = reg.json()["refresh_token"]

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