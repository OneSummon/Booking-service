from datetime import datetime, timedelta

import pytest


def _future_iso(start_days=10, duration=2):
    check_in = (datetime.utcnow() + timedelta(days=start_days)).isoformat()
    check_out = (datetime.utcnow() + timedelta(days=start_days + duration)).isoformat()
    return check_in, check_out


class TestCreateBooking:
    async def test_success(self, client, user_token, hotel_and_room):
        access_token, _ = user_token
        _, room_id = hotel_and_room
        check_in, check_out = _future_iso()
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["room_type_id"] == room_id
        assert "total_price" in body
        assert "id" in body

    async def test_requires_auth(self, client, hotel_and_room):
        _, room_id = hotel_and_room
        check_in, check_out = _future_iso()
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
        )
        assert resp.status_code == 401

    async def test_past_check_in_rejected(self, client, user_token, hotel_and_room):
        access_token, _ = user_token
        _, room_id = hotel_and_room
        check_in = (datetime.utcnow() - timedelta(days=1)).isoformat()
        check_out = (datetime.utcnow() + timedelta(days=1)).isoformat()
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 400

    async def test_guests_exceed_capacity_rejected(self, client, user_token, hotel_and_room):
        access_token, _ = user_token
        _, room_id = hotel_and_room
        check_in, check_out = _future_iso()
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 99},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 409

    async def test_nonexistent_room_rejected(self, client, user_token):
        access_token, _ = user_token
        check_in, check_out = _future_iso()
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": 999999, "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 404

    async def test_no_rooms_available(self, client, user_token, hotel_and_room):
        access_token, _ = user_token
        _, room_id = hotel_and_room
        check_in, check_out = _future_iso(start_days=50)
        # Book all 3 rooms
        for _ in range(3):
            r = await client.post(
                "/api/v1/bookings",
                json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert r.status_code == 201
        # 4th request must fail
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 409

    async def test_total_price_calculated_correctly(self, client, user_token, hotel_and_room):
        """2-night stay at 100.00/night = 200.00 total."""
        access_token, _ = user_token
        _, room_id = hotel_and_room
        check_in, check_out = _future_iso(duration=2)
        resp = await client.post(
            "/api/v1/bookings",
            json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 201
        assert float(resp.json()["total_price"]) == 200.00


class TestGetMyBookings:
    async def test_success(self, client, user_token, user_booking):
        access_token, _ = user_token
        resp = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/bookings")
        assert resp.status_code == 401

    async def test_returns_empty_when_no_bookings(self, client, user_token):
        access_token, _ = user_token
        resp = await client.get(
            "/api/v1/bookings",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetSpecificBooking:
    async def test_success(self, client, user_token, user_booking):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        resp = await client.get(
            f"/api/v1/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == booking_id

    async def test_not_found(self, client, user_token):
        access_token, _ = user_token
        resp = await client.get(
            "/api/v1/bookings/999999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 404

    async def test_other_users_booking_forbidden(self, client, user_booking):
        await client.post("/api/v1/auth/register", json={"email": "other@test.com", "password": "password123"})
        resp2 = await client.post("/api/v1/auth/login", data={"username": "other@test.com", "password": "password123"})
        other_token = resp2.json()["access_token"]

        resp = await client.get(
            f"/api/v1/bookings/{user_booking['id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


class TestCancelBooking:
    async def test_success(self, client, user_token, user_booking):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        resp = await client.post(
            f"/api/v1/bookings/{booking_id}/cancel",
            json={"cancellation_reason": "Changed plans"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["cancellation_reason"] == "Changed plans"

    async def test_already_cancelled_rejected(self, client, user_token, user_booking):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        await client.post(
            f"/api/v1/bookings/{booking_id}/cancel", json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp = await client.post(
            f"/api/v1/bookings/{booking_id}/cancel", json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 400

    async def test_requires_auth(self, client, user_booking):
        resp = await client.post(
            f"/api/v1/bookings/{user_booking['id']}/cancel", json={}
        )
        assert resp.status_code == 401

    async def test_other_users_booking_forbidden(self, client, user_booking):
        await client.post("/api/v1/auth/register", json={"email": "thief@test.com", "password": "password123"})
        resp2 = await client.post("/api/v1/auth/login", data={"username": "thief@test.com", "password": "password123"})
        thief_token = resp2.json()["access_token"]

        resp = await client.post(
            f"/api/v1/bookings/{user_booking['id']}/cancel",
            json={},
            headers={"Authorization": f"Bearer {thief_token}"},
        )
        assert resp.status_code == 403

    async def test_cancel_without_reason(self, client, user_token, user_booking):
        access_token, _ = user_token
        resp = await client.post(
            f"/api/v1/bookings/{user_booking['id']}/cancel",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["cancellation_reason"] is None
