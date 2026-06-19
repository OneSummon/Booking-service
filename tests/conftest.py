import os

# Must run before any app module is imported.
# pydantic-settings gives env vars priority over .env file, so these
# override production values and make the test suite self-contained.
os.environ.setdefault("DB_URL", "postgresql+asyncpg://test:test246@localhost:5432/booking_service_test")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_DB", "booking_service_test")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("EXPIRE_ACCESS_TOKEN_MIN", "30")
os.environ.setdefault("EXPIRE_REFRESH_TOKEN_DAYS", "7")
os.environ.setdefault("MAX_ACTIVE_SESSIONS", "3")
os.environ.setdefault("YOOKASSA_SHOP_ID", "test-shop-id")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test-yookassa-secret")
os.environ.setdefault("RETURN_URL", "http://localhost/return")
os.environ.setdefault("RATE_LIMITING_STORAGE", "memory://")
os.environ.setdefault("CACHE_STORAGE", "redis://localhost:6379/0")
os.environ.setdefault("TASKS_STORAGE", "memory://")
os.environ.setdefault("MAIL_SERVER", "smtp.example.com")
os.environ.setdefault("MAIL_PORT", "587")
os.environ.setdefault("MAIL_USERNAME", "test@example.com")
os.environ.setdefault("MAIL_PASSWORD", "test-mail-password")
os.environ.setdefault("MAIL_FROM", "noreply@example.com")
os.environ.setdefault("TTL_PENDING_BOOKINGS", "30")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("VERIFY_WEBHOOK_IP", "false")

import asyncio

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def test_engine():
    """
    Synchronous session-scoped fixture.

    NullPool is required: with a pool, connections created during setup are
    tied to the setup event loop. Each test runs in its own function-scoped
    loop, so pool reuse raises "Future attached to a different loop". NullPool
    creates a fresh connection on every acquire and closes it on release,
    so each test's loop gets its own connection.
    """
    from app.config import settings
    from app.database.models import Base

    engine = create_async_engine(settings.db_url, poolclass=NullPool)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_setup())
    yield engine
    asyncio.run(_teardown())
