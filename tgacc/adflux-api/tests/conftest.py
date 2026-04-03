"""
Shared fixtures for AdFlux API integration tests.

Uses an in-memory SQLite database so tests run fast and without
requiring a PostgreSQL instance.  All tables are created fresh for
every test function, and dependency overrides inject the test DB
session + fake authenticated users.
"""

# ---------------------------------------------------------------------------
# Patch PostgreSQL UUID type for SQLite *before* any model/app imports.
# ---------------------------------------------------------------------------

import uuid as _uuid_mod
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
from sqlalchemy.ext.compiler import compiles


@compiles(_PG_UUID, "sqlite")
def _compile_pg_uuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID columns as CHAR(36) in SQLite."""
    return "CHAR(36)"


_orig_bind = _PG_UUID.bind_processor
_orig_result = _PG_UUID.result_processor


def _patched_bind(self, dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return value
            return str(value)
        return process
    return _orig_bind(self, dialect)


def _patched_result(self, dialect, coltype):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return value
            if isinstance(value, _uuid_mod.UUID):
                return value
            return _uuid_mod.UUID(str(value))
        return process
    return _orig_result(self, dialect, coltype)


_PG_UUID.bind_processor = _patched_bind
_PG_UUID.result_processor = _patched_result

# ---------------------------------------------------------------------------
# Now safe to import application code
# ---------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models import (
    Base, AdminUser, Client, ClientUser, Wallet,
    SubscriptionPlan, AdAccount,
)
from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin


# ---------------------------------------------------------------------------
# Test database (in-memory SQLite via aiosqlite)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite://"

_test_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    """Create all tables before each test, drop them after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db():
    """Dependency override that yields a test DB session."""
    async with _TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Well-known IDs used across fixtures
# ---------------------------------------------------------------------------

ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CLIENT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
CLIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _seed_admin(session: AsyncSession) -> AdminUser:
    from passlib.hash import bcrypt

    admin = AdminUser(
        id=ADMIN_ID,
        email="admin@test.com",
        name="Test Admin",
        password_hash=bcrypt.hash("adminpass123"),
        role="admin",
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return admin


async def _seed_client_org(session: AsyncSession) -> Client:
    client = Client(id=CLIENT_ORG_ID, name="Test Corp", email="corp@test.com")
    session.add(client)
    await session.flush()
    return client


async def _seed_client_user(session: AsyncSession) -> ClientUser:
    from passlib.hash import bcrypt

    user = ClientUser(
        id=CLIENT_USER_ID,
        client_id=CLIENT_ORG_ID,
        email="client@test.com",
        name="Test Client",
        password_hash=bcrypt.hash("clientpass123"),
        role="viewer",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Fake auth dependency overrides
# ---------------------------------------------------------------------------

def _make_client_user_dict() -> dict:
    return {
        "id": str(CLIENT_USER_ID),
        "email": "client@test.com",
        "name": "Test Client",
        "role": "viewer",
        "user_type": "client",
        "client_id": str(CLIENT_ORG_ID),
        "is_active": True,
    }


def _make_admin_user_dict() -> dict:
    return {
        "id": str(ADMIN_ID),
        "email": "admin@test.com",
        "name": "Test Admin",
        "role": "admin",
        "user_type": "admin",
        "client_id": None,
        "is_active": True,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def seed_db():
    """Seed the test DB with an admin, a client org, and a client user."""
    async with _TestSession() as session:
        await _seed_admin(session)
        await _seed_client_org(session)
        await _seed_client_user(session)
        await session.commit()


@pytest_asyncio.fixture
async def seed_plan():
    """Seed a subscription plan and return its slug."""
    async with _TestSession() as session:
        plan = SubscriptionPlan(
            name="Starter",
            slug="starter",
            description="Basic plan",
            price_monthly=Decimal("49"),
            price_semiannual=Decimal("249"),
            price_annual=Decimal("449"),
            platforms=["facebook"],
            max_accounts=5,
            cashback_percent=Decimal("0"),
            features=["basic support"],
            is_active=True,
            sort_order=1,
        )
        session.add(plan)
        await session.commit()
    return "starter"


@pytest_asyncio.fixture
async def seed_wallet():
    """Create a wallet for the test client with $500 balance."""
    async with _TestSession() as session:
        wallet = Wallet(
            client_id=CLIENT_ORG_ID,
            currency="USD",
            balance=Decimal("500"),
            frozen_balance=Decimal("0"),
        )
        session.add(wallet)
        await session.commit()


@pytest_asyncio.fixture
async def seed_ad_account():
    """Create an ad account for the test client."""
    ad_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
    async with _TestSession() as session:
        account = AdAccount(
            id=ad_id,
            client_id=CLIENT_ORG_ID,
            platform="facebook",
            name="Test Ad Account",
            status="active",
            balance=Decimal("0"),
        )
        session.add(account)
        await session.commit()
    return ad_id


# ── HTTP clients with different auth contexts ──

CSRF_HEADER = {"X-CSRF-Token": "test-csrf-token"}


@pytest_asyncio.fixture
async def client():
    """Unauthenticated async HTTP test client."""
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin, None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers=CSRF_HEADER,
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client():
    """HTTP client authenticated as a regular client user."""
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_client_user_dict()
    app.dependency_overrides.pop(require_admin, None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={**CSRF_HEADER, "Authorization": "Bearer fake-client-token"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client():
    """HTTP client authenticated as an admin user."""
    admin_dict = _make_admin_user_dict()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin_dict
    app.dependency_overrides[require_admin] = lambda: admin_dict
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={**CSRF_HEADER, "Authorization": "Bearer fake-admin-token"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
