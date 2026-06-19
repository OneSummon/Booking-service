import pytest


class TestRegister:
    async def test_success(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@test.com", "password": "password123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@test.com"
        assert "id" in body
        assert "password_hash" not in body
        assert body["role"] == "user"

    async def test_duplicate_email_rejected(self, client):
        data = {"email": "dup@test.com", "password": "password123"}
        await client.post("/api/v1/auth/register", json=data)
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 400

    async def test_invalid_email_format(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    async def test_short_password_rejected(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_email_stored_lowercase(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "UPPER@TEST.COM", "password": "password123"},
        )
        assert resp.status_code == 201
        assert resp.json()["email"] == "upper@test.com"


class TestLogin:
    async def test_success_returns_tokens(self, client, user_token):
        access_token, refresh_token = user_token
        assert isinstance(access_token, str) and len(access_token) > 0
        assert isinstance(refresh_token, str) and len(refresh_token) > 0

    async def test_wrong_password(self, client):
        await client.post("/api/v1/auth/register", json={"email": "u@test.com", "password": "pass1234"})
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "u@test.com", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_unknown_email(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@test.com", "password": "pass"},
        )
        assert resp.status_code == 401

    async def test_response_has_token_type(self, client, user_token):
        # login response is checked inside user_token fixture; verify schema
        await client.post("/api/v1/auth/register", json={"email": "schema@test.com", "password": "pass1234"})
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "schema@test.com", "password": "pass1234"},
        )
        assert resp.json()["token_type"] == "bearer"


class TestRefresh:
    async def test_success_returns_new_tokens(self, client, user_token):
        _, refresh_token = user_token
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_old_token_revoked_after_refresh(self, client, user_token):
        _, refresh_token = user_token
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    async def test_unknown_token(self, client):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "unknown-token-xyz"})
        assert resp.status_code == 401

    async def test_new_token_is_usable(self, client, user_token):
        _, refresh_token = user_token
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        new_access = resp.json()["access_token"]
        profile_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert profile_resp.status_code == 200


class TestLogout:
    async def test_success(self, client, user_token):
        access_token, refresh_token = user_token
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 202

    async def test_requires_auth(self, client, user_token):
        _, refresh_token = user_token
        resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    async def test_token_unusable_after_logout(self, client, user_token):
        access_token, refresh_token = user_token
        await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 400
