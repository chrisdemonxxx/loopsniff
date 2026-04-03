"""Integration tests for /auth/* endpoints."""

import pytest
from tests.conftest import ADMIN_ID, CLIENT_USER_ID

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post("/auth/register", json={
            "email": "newuser@example.com",
            "password": "Str0ngP@ss!",
            "name": "New User",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_type"] == "client"
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["name"] == "New User"

    async def test_register_duplicate_email(self, client, seed_db):
        resp = await client.post("/auth/register", json={
            "email": "client@test.com",
            "password": "AnyP@ss1",
            "name": "Dup",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    async def test_register_admin_forbidden(self, client):
        resp = await client.post("/auth/register", json={
            "email": "hack@evil.com",
            "password": "whatever",
            "name": "Hacker",
            "user_type": "admin",
        })
        assert resp.status_code == 403

    async def test_register_missing_fields(self, client):
        resp = await client.post("/auth/register", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_valid_client(self, client, seed_db):
        resp = await client.post("/auth/login", json={
            "email": "client@test.com",
            "password": "clientpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_type"] == "client"
        assert data["user_id"] == str(CLIENT_USER_ID)
        assert "access_token" in data

    async def test_login_valid_admin(self, client, seed_db):
        resp = await client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_type"] == "admin"
        assert data["user_id"] == str(ADMIN_ID)

    async def test_login_wrong_password(self, client, seed_db):
        resp = await client.post("/auth/login", json={
            "email": "client@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client, seed_db):
        resp = await client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever",
        })
        assert resp.status_code == 401

    async def test_login_missing_body(self, client):
        resp = await client.post("/auth/login")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_refresh_with_valid_token(self, client, seed_db):
        # First login to get a real refresh token
        login = await client.post("/auth/login", json={
            "email": "client@test.com",
            "password": "clientpass123",
        })
        refresh_token = login.json()["refresh_token"]

        resp = await client.post("/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user_type"] == "client"

    async def test_refresh_with_invalid_token(self, client):
        resp = await client.post("/auth/refresh", json={
            "refresh_token": "garbage-token",
        })
        assert resp.status_code == 401

    async def test_refresh_missing_body(self, client):
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_unauthenticated(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)

    async def test_me_as_client(self, auth_client, seed_db):
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "client@test.com"
        assert data["user_type"] == "client"
        assert data["is_active"] is True

    async def test_me_as_admin(self, admin_client, seed_db):
        resp = await admin_client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_type"] == "admin"


# ---------------------------------------------------------------------------
# Password reset flow
# ---------------------------------------------------------------------------


class TestPasswordReset:
    async def test_forgot_password_always_succeeds(self, client, seed_db):
        # Existing email — should return generic message (not leak token)
        resp = await client.post("/auth/forgot-password", json={
            "email": "client@test.com",
        })
        assert resp.status_code == 200
        assert "message" in resp.json()
        assert "reset_token" not in resp.json()  # Token is emailed, not returned

    async def test_forgot_password_unknown_email(self, client, seed_db):
        resp = await client.post("/auth/forgot-password", json={
            "email": "nonexistent@example.com",
        })
        assert resp.status_code == 200
        # Must NOT leak whether email exists
        assert "reset_token" not in resp.json()

    async def test_reset_password_with_valid_token(self, client, seed_db):
        # Create token directly (forgot-password emails it, doesn't return it)
        from app.auth.jwt import create_reset_token
        token = create_reset_token("client@test.com")

        resp = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "NewStr0ng!Pass",
        })
        assert resp.status_code == 200
        assert "reset successfully" in resp.json()["message"].lower()

        # Verify new password works
        login = await client.post("/auth/login", json={
            "email": "client@test.com",
            "password": "NewStr0ng!Pass",
        })
        assert login.status_code == 200

    async def test_reset_password_invalid_token(self, client):
        resp = await client.post("/auth/reset-password", json={
            "token": "bad-token",
            "new_password": "irrelevant",
        })
        assert resp.status_code == 400
