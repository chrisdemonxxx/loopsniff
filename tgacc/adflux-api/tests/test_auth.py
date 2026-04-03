import pytest

pytestmark = pytest.mark.asyncio


class TestAuthLogin:
    """Tests for POST /auth/login."""

    async def test_login_missing_body(self, client):
        response = await client.post("/auth/login")
        assert response.status_code == 422

    async def test_login_invalid_credentials(self, client):
        response = await client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )
        assert response.status_code in (401, 404, 422, 500)

    async def test_login_empty_email(self, client):
        response = await client.post(
            "/auth/login",
            json={"email": "", "password": "somepass"},
        )
        assert response.status_code in (401, 422)


class TestAuthRegister:
    """Tests for POST /auth/register."""

    async def test_register_missing_body(self, client):
        response = await client.post("/auth/register")
        assert response.status_code == 422

    async def test_register_invalid_email(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "StrongP@ss1",
                "full_name": "Test",
            },
        )
        assert response.status_code == 422


class TestAuthRefresh:
    """Tests for POST /auth/refresh."""

    async def test_refresh_missing_token(self, client):
        response = await client.post("/auth/refresh")
        assert response.status_code in (401, 422)

    async def test_refresh_invalid_token(self, client):
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code in (401, 422, 500)


class TestAuthPasswordReset:
    """Tests for password-reset flow."""

    async def test_forgot_password_missing_body(self, client):
        response = await client.post("/auth/forgot-password")
        assert response.status_code == 422

    async def test_reset_password_missing_body(self, client):
        response = await client.post("/auth/reset-password")
        assert response.status_code == 422

    async def test_reset_password_invalid_token(self, client):
        response = await client.post(
            "/auth/reset-password",
            json={"token": "bad", "new_password": "NewP@ss1"},
        )
        assert response.status_code in (400, 401, 422, 500)


class TestAuthMe:
    """Tests for GET /auth/me."""

    async def test_me_no_auth(self, client):
        response = await client.get("/auth/me")
        assert response.status_code in (401, 403)

    async def test_me_invalid_token(self, client):
        response = await client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code in (401, 403)
