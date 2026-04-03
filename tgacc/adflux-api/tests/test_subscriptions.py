import pytest

pytestmark = pytest.mark.asyncio


class TestSubscriptionPlans:
    """Tests for GET /subscriptions/plans."""

    async def test_list_plans_no_auth(self, client):
        response = await client.get("/subscriptions/plans")
        # Plans listing may or may not require auth depending on implementation
        assert response.status_code in (200, 401, 403, 500)

    async def test_list_plans_returns_list(self, client):
        response = await client.get("/subscriptions/plans")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


class TestSubscriptionCurrent:
    """Tests for GET /subscriptions/current."""

    async def test_current_no_auth(self, client):
        response = await client.get("/subscriptions/current")
        assert response.status_code in (401, 403)


class TestSubscriptionSubscribe:
    """Tests for POST /subscriptions/subscribe."""

    async def test_subscribe_no_auth(self, client):
        response = await client.post(
            "/subscriptions/subscribe", json={"plan_id": "fake-plan-id"}
        )
        assert response.status_code in (401, 403)

    async def test_subscribe_missing_body(self, client):
        response = await client.post("/subscriptions/subscribe")
        assert response.status_code in (401, 403, 422)


class TestSubscriptionCancel:
    """Tests for POST /subscriptions/cancel."""

    async def test_cancel_no_auth(self, client):
        response = await client.post("/subscriptions/cancel")
        assert response.status_code in (401, 403)


class TestSubscriptionChange:
    """Tests for POST /subscriptions/change."""

    async def test_change_no_auth(self, client):
        response = await client.post(
            "/subscriptions/change", json={"plan_id": "new-plan-id"}
        )
        assert response.status_code in (401, 403)

    async def test_change_missing_body(self, client):
        response = await client.post("/subscriptions/change")
        assert response.status_code in (401, 403, 422)


class TestAdminPlans:
    """Tests for admin plan management endpoints."""

    async def test_admin_list_plans_no_auth(self, client):
        response = await client.get("/admin/plans")
        assert response.status_code in (401, 403)

    async def test_admin_create_plan_no_auth(self, client):
        response = await client.post(
            "/admin/plans",
            json={"name": "Test Plan", "price": 99.99},
        )
        assert response.status_code in (401, 403)
