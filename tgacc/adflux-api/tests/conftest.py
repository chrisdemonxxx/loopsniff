import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    """Async HTTP test client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def mock_user():
    """Fake client-user payload for tests that need an authenticated user."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "testuser@example.com",
        "full_name": "Test User",
        "role": "client",
    }


@pytest.fixture
def mock_admin():
    """Fake admin-user payload for tests that need admin privileges."""
    return {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": "admin",
    }


@pytest.fixture
def auth_headers():
    """Returns a helper that builds an Authorization header from a token."""
    def _headers(token: str = "test-token"):
        return {"Authorization": f"Bearer {token}"}
    return _headers
