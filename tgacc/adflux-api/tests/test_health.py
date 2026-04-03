import pytest

pytestmark = pytest.mark.asyncio


class TestRoot:
    async def test_root_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_root_structure(self, client):
        data = (await client.get("/")).json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert "service" in data


class TestHealth:
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_structure(self, client):
        data = (await client.get("/health")).json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"


class TestDocs:
    async def test_openapi_json(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "AdFlux API"
        assert "paths" in schema
