"""Integration tests for /subscriptions/* endpoints."""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /subscriptions/plans  (public — no auth required)
# ---------------------------------------------------------------------------


class TestListPlans:
    async def test_plans_returns_list(self, client, seed_db):
        resp = await client.get("/subscriptions/plans")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_plans_includes_seeded(self, client, seed_db, seed_plan):
        resp = await client.get("/subscriptions/plans")
        plans = resp.json()
        slugs = [p["slug"] for p in plans]
        assert "starter" in slugs

    async def test_plan_fields(self, client, seed_db, seed_plan):
        plans = (await client.get("/subscriptions/plans")).json()
        plan = next(p for p in plans if p["slug"] == "starter")
        assert float(plan["price_monthly"]) == 49
        assert plan["is_active"] is True
        assert "features" in plan


# ---------------------------------------------------------------------------
# POST /subscriptions/subscribe
# ---------------------------------------------------------------------------


class TestSubscribe:
    async def test_subscribe_requires_auth(self, client):
        resp = await client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter",
        })
        assert resp.status_code in (401, 403)

    async def test_subscribe_success(self, auth_client, seed_db, seed_plan):
        resp = await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter",
            "interval": "monthly",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["plan"] == "starter"
        assert data["status"] == "active"
        assert data["interval_type"] == "monthly"
        assert float(data["price"]) == 49

    async def test_subscribe_nonexistent_plan(self, auth_client, seed_db):
        resp = await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "nonexistent",
            "interval": "monthly",
        })
        assert resp.status_code == 404

    async def test_subscribe_invalid_interval(self, auth_client, seed_db, seed_plan):
        resp = await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter",
            "interval": "weekly",
        })
        assert resp.status_code == 400

    async def test_subscribe_cancels_previous(self, auth_client, seed_db, seed_plan):
        # Subscribe once
        first = await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter", "interval": "monthly",
        })
        assert first.status_code == 201

        # Subscribe again (should auto-cancel old)
        second = await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter", "interval": "annual",
        })
        assert second.status_code == 201
        assert second.json()["interval_type"] == "annual"


# ---------------------------------------------------------------------------
# GET /subscriptions/current
# ---------------------------------------------------------------------------


class TestCurrentSubscription:
    async def test_current_requires_auth(self, client):
        resp = await client.get("/subscriptions/current")
        assert resp.status_code in (401, 403)

    async def test_current_no_subscription(self, auth_client, seed_db):
        resp = await auth_client.get("/subscriptions/current")
        assert resp.status_code == 404

    async def test_current_after_subscribe(self, auth_client, seed_db, seed_plan):
        await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter", "interval": "monthly",
        })
        resp = await auth_client.get("/subscriptions/current")
        assert resp.status_code == 200
        assert resp.json()["plan"] == "starter"


# ---------------------------------------------------------------------------
# POST /subscriptions/cancel
# ---------------------------------------------------------------------------


class TestCancelSubscription:
    async def test_cancel_requires_auth(self, client):
        resp = await client.post("/subscriptions/cancel", json={})
        assert resp.status_code in (401, 403)

    async def test_cancel_no_active_sub(self, auth_client, seed_db):
        resp = await auth_client.post("/subscriptions/cancel", json={
            "reason": "testing",
        })
        assert resp.status_code == 404

    async def test_cancel_success(self, auth_client, seed_db, seed_plan):
        await auth_client.post("/subscriptions/subscribe", json={
            "plan_slug": "starter", "interval": "monthly",
        })
        resp = await auth_client.post("/subscriptions/cancel", json={
            "reason": "not needed",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify no active sub remains
        current = await auth_client.get("/subscriptions/current")
        assert current.status_code == 404


# ---------------------------------------------------------------------------
# Admin plan management
# ---------------------------------------------------------------------------


class TestAdminPlans:
    async def test_admin_create_plan(self, admin_client, seed_db):
        resp = await admin_client.post("/admin/plans", json={
            "name": "Pro",
            "slug": "pro",
            "price_monthly": 99,
            "features": ["priority support"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "pro"
        assert data["is_active"] is True

    async def test_admin_list_plans(self, admin_client, seed_db, seed_plan):
        resp = await admin_client.get("/admin/plans")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_admin_plans_requires_admin(self, auth_client, seed_db):
        resp = await auth_client.get("/admin/plans")
        assert resp.status_code == 403
