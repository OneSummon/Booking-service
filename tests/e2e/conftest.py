import itertools
from datetime import datetime, timedelta

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


_ip_counter = itertools.count(1)


class _UniqueIPClient(AsyncClient):
    """Injects a unique X-Real-IP header per request to avoid rate limit collisions."""

    async def request(self, method, url, *, headers=None, **kwargs):
        headers = dict(headers) if headers else {}
        if not any(k.lower() == "x-real-ip" for k in headers):
            n = next(_ip_counter)
            headers["X-Real-IP"] = f"10.{(n // 65536) % 256}.{(n // 256) % 256}.{n % 256}"
        return await super().request(method, url, headers=headers, **kwargs)


@pytest.fixture
async def client(test_engine):
    from app.database.database import get_session
    from main import app

    # ASGITransport does not invoke the ASGI lifespan protocol, so FastAPICache
    # is never initialized via the production lifespan. Initialize it directly.
    FastAPICache.init(InMemoryBackend(), prefix="test-cache")

    async with test_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE refresh_tokens, payments, bookings, room_types, hotels, users"
            " RESTART IDENTITY CASCADE"
        ))

    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    async with _UniqueIPClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_send_email(mocker):
    return mocker.patch("app.celery_app.send_email.delay")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def user_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@test.com", "password": "password123"},
    )
    data = resp.json()
    return data["access_token"], data["refresh_token"]


@pytest.fixture
async def admin_token(client, test_engine):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "password": "adminpass123"},
    )
    async with test_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET role = 'admin' WHERE email = 'admin@test.com'")
        )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "adminpass123"},
    )
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def hotel_and_room(client, admin_token):
    hotel_resp = await client.post(
        "/api/v1/admin/hotels",
        json={
            "name": "Test Hotel", "city": "Moscow", "country": "Russia",
            "star_rating": 4.0, "description": "Test hotel", "address": "1 Main St",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    hotel_id = hotel_resp.json()["id"]

    room_resp = await client.post(
        f"/api/v1/admin/hotels/{hotel_id}/room-types",
        json={
            "name": "Standard", "capacity": 2, "bed_type": "double",
            "price_per_night": "100.00", "total_rooms": 3,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    room_id = room_resp.json()["id"]
    return hotel_id, room_id


@pytest.fixture
async def user_booking(client, user_token, hotel_and_room):
    access_token, _ = user_token
    _, room_id = hotel_and_room
    check_in = (datetime.utcnow() + timedelta(days=10)).isoformat()
    check_out = (datetime.utcnow() + timedelta(days=12)).isoformat()
    resp = await client.post(
        "/api/v1/bookings",
        json={
            "room_type_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "guests_count": 1,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return resp.json()
