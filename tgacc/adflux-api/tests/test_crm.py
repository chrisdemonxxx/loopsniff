"""Integration tests for /crm/* endpoints (admin-only)."""

import pytest
from tests.conftest import ADMIN_ID

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /crm/leads  — create lead
# ---------------------------------------------------------------------------


class TestCreateLead:
    async def test_create_lead_success(self, admin_client, seed_db):
        resp = await admin_client.post("/crm/leads", json={
            "name": "Jane Doe",
            "email": "jane@corp.com",
            "company": "Corp Inc",
            "source": "linkedin",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Jane Doe"
        assert data["status"] == "new"
        assert data["priority"] == "medium"
        assert data["bant_score"] == 0

    async def test_create_lead_with_bant(self, admin_client, seed_db):
        resp = await admin_client.post("/crm/leads", json={
            "name": "BANT Lead",
            "budget": "$5000/mo",
            "authority": "CEO",
            "need": "Ad accounts",
            "timeline": "This month",
        })
        assert resp.status_code == 201
        assert resp.json()["bant_score"] == 100  # all 4 fields → 25*4

    async def test_create_lead_partial_bant(self, admin_client, seed_db):
        resp = await admin_client.post("/crm/leads", json={
            "name": "Partial",
            "budget": "$1000",
            "need": "Scaling ads",
        })
        assert resp.status_code == 201
        assert resp.json()["bant_score"] == 50  # 2 of 4 → 50

    async def test_create_lead_requires_admin(self, auth_client, seed_db):
        resp = await auth_client.post("/crm/leads", json={"name": "X"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /crm/leads  — list leads
# ---------------------------------------------------------------------------


class TestListLeads:
    async def test_list_empty(self, admin_client, seed_db):
        resp = await admin_client.get("/crm/leads")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_after_create(self, admin_client, seed_db):
        await admin_client.post("/crm/leads", json={"name": "Lead 1"})
        await admin_client.post("/crm/leads", json={"name": "Lead 2"})
        resp = await admin_client.get("/crm/leads")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_filter_by_status(self, admin_client, seed_db):
        await admin_client.post("/crm/leads", json={
            "name": "Qualified", "status": "qualified",
        })
        await admin_client.post("/crm/leads", json={"name": "New"})
        resp = await admin_client.get("/crm/leads", params={"status": "qualified"})
        leads = resp.json()
        assert len(leads) == 1
        assert leads[0]["name"] == "Qualified"

    async def test_list_requires_admin(self, auth_client, seed_db):
        resp = await auth_client.get("/crm/leads")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /crm/leads/{id}  — update lead
# ---------------------------------------------------------------------------


class TestUpdateLead:
    async def test_update_lead_status(self, admin_client, seed_db):
        create = await admin_client.post("/crm/leads", json={"name": "UpdTest"})
        lead_id = create.json()["id"]

        resp = await admin_client.put(f"/crm/leads/{lead_id}", json={
            "status": "qualified",
            "priority": "high",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "qualified"
        assert resp.json()["priority"] == "high"

    async def test_update_recalculates_bant(self, admin_client, seed_db):
        create = await admin_client.post("/crm/leads", json={"name": "BANTTest"})
        lead_id = create.json()["id"]
        assert create.json()["bant_score"] == 0

        resp = await admin_client.put(f"/crm/leads/{lead_id}", json={
            "budget": "$3000",
            "authority": "VP",
        })
        assert resp.json()["bant_score"] == 50

    async def test_update_nonexistent(self, admin_client, seed_db):
        resp = await admin_client.put(
            "/crm/leads/99999999-9999-9999-9999-999999999999",
            json={"status": "won"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /crm/leads/{id}
# ---------------------------------------------------------------------------


class TestDeleteLead:
    async def test_delete_success(self, admin_client, seed_db):
        create = await admin_client.post("/crm/leads", json={"name": "ToDelete"})
        lead_id = create.json()["id"]

        resp = await admin_client.delete(f"/crm/leads/{lead_id}")
        assert resp.status_code == 200

        get = await admin_client.get(f"/crm/leads/{lead_id}")
        assert get.status_code == 404

    async def test_delete_nonexistent(self, admin_client, seed_db):
        resp = await admin_client.delete(
            "/crm/leads/99999999-9999-9999-9999-999999999999",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /crm/leads/stats
# ---------------------------------------------------------------------------


class TestLeadStats:
    async def test_stats_empty(self, admin_client, seed_db):
        resp = await admin_client.get("/crm/leads/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["avg_bant_score"] == 0

    async def test_stats_with_data(self, admin_client, seed_db):
        await admin_client.post("/crm/leads", json={
            "name": "A", "source": "linkedin", "budget": "$1k",
        })
        await admin_client.post("/crm/leads", json={
            "name": "B", "source": "telegram",
        })
        resp = await admin_client.get("/crm/leads/stats")
        data = resp.json()
        assert data["total"] == 2
        assert "by_source" in data
        assert "by_status" in data


# ---------------------------------------------------------------------------
# POST /crm/leads/bulk  — bulk import
# ---------------------------------------------------------------------------


class TestBulkImport:
    async def test_bulk_create(self, admin_client, seed_db):
        resp = await admin_client.post("/crm/leads/bulk", json={
            "leads": [
                {"name": "Bulk1", "email": "b1@test.com"},
                {"name": "Bulk2", "email": "b2@test.com"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] == 2
        assert data["updated"] == 0

    async def test_bulk_upsert(self, admin_client, seed_db):
        # First import
        await admin_client.post("/crm/leads/bulk", json={
            "leads": [{"name": "Upsert", "email": "ups@test.com"}],
        })
        # Second import same email → should update
        resp = await admin_client.post("/crm/leads/bulk", json={
            "leads": [{"name": "Upsert Updated", "email": "ups@test.com"}],
        })
        assert resp.status_code == 201
        assert resp.json()["updated"] == 1
        assert resp.json()["created"] == 0
