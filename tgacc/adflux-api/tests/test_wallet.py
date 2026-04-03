"""Integration tests for /wallet/* endpoints."""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /wallet — balance
# ---------------------------------------------------------------------------


class TestWalletBalance:
    async def test_wallet_requires_auth(self, client):
        resp = await client.get("/wallet")
        assert resp.status_code in (401, 403)

    async def test_wallet_auto_creates(self, auth_client, seed_db):
        resp = await auth_client.get("/wallet")
        assert resp.status_code == 200
        data = resp.json()
        assert "balance" in data
        assert "currency" in data
        assert float(data["balance"]) == 0

    async def test_wallet_returns_seeded_balance(self, auth_client, seed_db, seed_wallet):
        resp = await auth_client.get("/wallet")
        assert resp.status_code == 200
        assert float(resp.json()["balance"]) == 500


# ---------------------------------------------------------------------------
# POST /wallet/deposit
# ---------------------------------------------------------------------------


class TestWalletDeposit:
    async def test_deposit_requires_auth(self, client):
        resp = await client.post("/wallet/deposit", json={
            "amount": 100, "payment_method": "crypto",
        })
        assert resp.status_code in (401, 403)

    async def test_deposit_success(self, auth_client, seed_db):
        resp = await auth_client.post("/wallet/deposit", json={
            "amount": 250,
            "currency": "USD",
            "payment_method": "crypto",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "deposit"
        assert data["status"] == "pending"
        assert float(data["amount"]) == 250

    async def test_deposit_invalid_payment_method(self, auth_client, seed_db):
        resp = await auth_client.post("/wallet/deposit", json={
            "amount": 100,
            "payment_method": "magic_beans",
        })
        assert resp.status_code == 400
        assert "invalid payment method" in resp.json()["detail"].lower()

    async def test_deposit_zero_amount(self, auth_client, seed_db):
        resp = await auth_client.post("/wallet/deposit", json={
            "amount": 0,
            "payment_method": "crypto",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /wallet/withdraw
# ---------------------------------------------------------------------------


class TestWalletWithdraw:
    async def test_withdraw_success(self, auth_client, seed_db, seed_wallet):
        resp = await auth_client.post("/wallet/withdraw", json={
            "amount": 100,
            "payment_method": "bank_transfer",
            "destination": "US1234567890",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "withdrawal"
        assert data["status"] == "pending"
        assert float(data["amount"]) == 100

    async def test_withdraw_insufficient_funds(self, auth_client, seed_db, seed_wallet):
        resp = await auth_client.post("/wallet/withdraw", json={
            "amount": 9999,
            "payment_method": "bank_transfer",
            "destination": "US1234567890",
        })
        assert resp.status_code == 400
        assert "insufficient" in resp.json()["detail"].lower()

    async def test_withdraw_freezes_balance(self, auth_client, seed_db, seed_wallet):
        # Withdraw 200
        await auth_client.post("/wallet/withdraw", json={
            "amount": 200,
            "payment_method": "crypto",
            "destination": "0xabc",
        })
        # Check wallet — frozen_balance should be 200
        wallet_resp = await auth_client.get("/wallet")
        data = wallet_resp.json()
        assert float(data["frozen_balance"]) == 200
        # Available = balance - frozen = 500 - 200 = 300
        # Trying to withdraw 400 should fail
        resp = await auth_client.post("/wallet/withdraw", json={
            "amount": 400,
            "payment_method": "crypto",
            "destination": "0xdef",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /wallet/transfer
# ---------------------------------------------------------------------------


class TestWalletTransfer:
    async def test_transfer_success(self, auth_client, seed_db, seed_wallet, seed_ad_account):
        resp = await auth_client.post("/wallet/transfer", json={
            "amount": 100,
            "target_account_id": "00000000-0000-0000-0000-000000000020",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "transfer"
        assert data["status"] == "completed"

        # Check wallet balance decreased
        wallet = (await auth_client.get("/wallet")).json()
        assert float(wallet["balance"]) == 400

    async def test_transfer_insufficient_funds(self, auth_client, seed_db, seed_wallet, seed_ad_account):
        resp = await auth_client.post("/wallet/transfer", json={
            "amount": 9999,
            "target_account_id": "00000000-0000-0000-0000-000000000020",
        })
        assert resp.status_code == 400

    async def test_transfer_nonexistent_account(self, auth_client, seed_db, seed_wallet):
        resp = await auth_client.post("/wallet/transfer", json={
            "amount": 10,
            "target_account_id": "99999999-9999-9999-9999-999999999999",
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /wallet/transactions
# ---------------------------------------------------------------------------


class TestWalletTransactions:
    async def test_transactions_empty(self, auth_client, seed_db):
        resp = await auth_client.get("/wallet/transactions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_transactions_after_deposit(self, auth_client, seed_db):
        # Create a deposit
        await auth_client.post("/wallet/deposit", json={
            "amount": 50,
            "payment_method": "crypto",
        })
        resp = await auth_client.get("/wallet/transactions")
        assert resp.status_code == 200
        txns = resp.json()
        assert len(txns) == 1
        assert txns[0]["type"] == "deposit"


# ---------------------------------------------------------------------------
# GET /wallet/deposit-config
# ---------------------------------------------------------------------------


class TestDepositConfig:
    async def test_deposit_config_requires_auth(self, client):
        resp = await client.get("/wallet/deposit-config")
        assert resp.status_code in (401, 403)

    async def test_deposit_config_returns_list(self, auth_client, seed_db):
        resp = await auth_client.get("/wallet/deposit-config")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
