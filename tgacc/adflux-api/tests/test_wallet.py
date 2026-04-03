import pytest

pytestmark = pytest.mark.asyncio


class TestWalletGet:
    """Tests for GET /wallet."""

    async def test_wallet_no_auth(self, client):
        response = await client.get("/wallet")
        assert response.status_code in (401, 403)

    async def test_wallet_invalid_token(self, client):
        response = await client.get(
            "/wallet", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code in (401, 403)


class TestWalletDeposit:
    """Tests for POST /wallet/deposit."""

    async def test_deposit_no_auth(self, client):
        response = await client.post("/wallet/deposit", json={"amount": 100})
        assert response.status_code in (401, 403)

    async def test_deposit_missing_body(self, client):
        response = await client.post("/wallet/deposit")
        assert response.status_code in (401, 403, 422)


class TestWalletTransactions:
    """Tests for GET /wallet/transactions."""

    async def test_transactions_no_auth(self, client):
        response = await client.get("/wallet/transactions")
        assert response.status_code in (401, 403)


class TestWalletBalance:
    """Tests for wallet balance via GET /wallet."""

    async def test_balance_requires_auth(self, client):
        response = await client.get("/wallet")
        assert response.status_code in (401, 403)


class TestWalletDepositConfig:
    """Tests for GET /wallet/deposit-config."""

    async def test_deposit_config_no_auth(self, client):
        response = await client.get("/wallet/deposit-config")
        assert response.status_code in (401, 403)
