import pytest


class TestGetMyProfile:
    async def test_success(self, client, user_token):
        access_token, _ = user_token
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@test.com"
        assert "password_hash" not in body
        assert body["role"] == "user"
        assert "created_at" in body

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401


class TestUpdateMyProfile:
    async def test_update_name(self, client, user_token):
        access_token, _ = user_token
        resp = await client.patch(
            "/api/v1/users/me",
            json={"first_name": "Ivan", "last_name": "Petrov"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["first_name"] == "Ivan"
        assert body["last_name"] == "Petrov"

    async def test_update_email(self, client, user_token):
        access_token, _ = user_token
        resp = await client.patch(
            "/api/v1/users/me",
            json={"email": "new_email@test.com"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new_email@test.com"

    async def test_duplicate_email_rejected(self, client, user_token):
        await client.post("/api/v1/auth/register", json={"email": "taken@test.com", "password": "password123"})
        access_token, _ = user_token
        resp = await client.patch(
            "/api/v1/users/me",
            json={"email": "taken@test.com"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 409

    async def test_requires_auth(self, client):
        resp = await client.patch("/api/v1/users/me", json={"first_name": "x"})
        assert resp.status_code == 401


class TestChangePassword:
    async def test_success(self, client, user_token):
        access_token, _ = user_token
        resp = await client.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "password123",
                "new_password": "newpassword123",
                "retry_new_password": "newpassword123",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 204

    async def test_revokes_refresh_token_after_change(self, client, user_token):
        access_token, refresh_token = user_token
        await client.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "password123",
                "new_password": "newpassword123",
                "retry_new_password": "newpassword123",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 400

    async def test_wrong_current_password(self, client, user_token):
        access_token, _ = user_token
        resp = await client.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
                "retry_new_password": "newpassword123",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 400

    async def test_new_passwords_mismatch(self, client, user_token):
        access_token, _ = user_token
        resp = await client.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "password123",
                "new_password": "newpassword123",
                "retry_new_password": "different123",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 400

    async def test_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/users/me/change-password",
            json={"current_password": "x", "new_password": "xxxxxxxx", "retry_new_password": "xxxxxxxx"},
        )
        assert resp.status_code == 401


class TestDeleteAccount:
    async def test_success(self, client, user_token):
        access_token, refresh_token = user_token
        resp = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 204

    async def test_requires_auth(self, client):
        resp = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"refresh_token": "some-token"},
        )
        assert resp.status_code == 401

    async def test_invalid_refresh_token_rejected(self, client, user_token):
        access_token, _ = user_token
        resp = await client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"refresh_token": "totally-wrong-token"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 404
