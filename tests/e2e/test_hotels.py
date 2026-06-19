from datetime import datetime, timedelta

import pytest


class TestGetAllHotels:
    async def test_empty_when_no_hotels(self, client):
        resp = await client.get("/api/v1/hotels")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_active_hotel(self, client, hotel_and_room):
        resp = await client.get("/api/v1/hotels")
        assert resp.status_code == 200
        hotels = resp.json()
        assert len(hotels) == 1
        assert hotels[0]["name"] == "Test Hotel"
        assert hotels[0]["is_active"] is True

    async def test_filters_by_city_match(self, client, hotel_and_room):
        resp = await client.get("/api/v1/hotels", params={"city": "Moscow"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_filters_by_city_no_match(self, client, hotel_and_room):
        resp = await client.get("/api/v1/hotels", params={"city": "Berlin"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_filters_by_star_rating(self, client, hotel_and_room):
        resp = await client.get("/api/v1/hotels", params={"min_star_rating": 5.0})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_inactive_hotel_not_returned(self, client, hotel_and_room, admin_token):
        hotel_id, _ = hotel_and_room
        await client.delete(
            f"/api/v1/admin/hotels/{hotel_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = await client.get("/api/v1/hotels")
        ids = [h["id"] for h in resp.json()]
        assert hotel_id not in ids


class TestGetHotelDetail:
    async def test_success(self, client, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.get(f"/api/v1/hotels/{hotel_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == hotel_id
        assert "room_types" in body
        assert len(body["room_types"]) == 1

    async def test_not_found(self, client):
        resp = await client.get("/api/v1/hotels/999999")
        assert resp.status_code == 404

    async def test_inactive_returns_404(self, client, hotel_and_room, admin_token):
        hotel_id, _ = hotel_and_room
        await client.delete(
            f"/api/v1/admin/hotels/{hotel_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = await client.get(f"/api/v1/hotels/{hotel_id}")
        assert resp.status_code == 404


class TestGetRoomTypes:
    async def test_success(self, client, hotel_and_room):
        hotel_id, room_id = hotel_and_room
        resp = await client.get(f"/api/v1/hotels/{hotel_id}/room-types")
        assert resp.status_code == 200
        rooms = resp.json()
        assert len(rooms) == 1
        assert rooms[0]["id"] == room_id
        assert rooms[0]["name"] == "Standard"

    async def test_hotel_not_found(self, client):
        resp = await client.get("/api/v1/hotels/999999/room-types")
        assert resp.status_code == 404


class TestAvailability:
    def _dates(self, start=10, duration=2):
        check_in = (datetime.utcnow() + timedelta(days=start)).isoformat()
        check_out = (datetime.utcnow() + timedelta(days=start + duration)).isoformat()
        return {"req_check_in": check_in, "req_check_out": check_out}

    async def test_available(self, client, hotel_and_room):
        hotel_id, room_id = hotel_and_room
        resp = await client.get(
            f"/api/v1/hotels/{hotel_id}/room-types/{room_id}/availability",
            params=self._dates(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["count_available_rooms"] == 3

    async def test_fully_booked(self, client, hotel_and_room, user_token):
        hotel_id, room_id = hotel_and_room
        access_token, _ = user_token
        # Book all 3 rooms
        check_in = (datetime.utcnow() + timedelta(days=50)).isoformat()
        check_out = (datetime.utcnow() + timedelta(days=52)).isoformat()
        for _ in range(3):
            await client.post(
                "/api/v1/bookings",
                json={"room_type_id": room_id, "check_in": check_in, "check_out": check_out, "guests_count": 1},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        resp = await client.get(
            f"/api/v1/hotels/{hotel_id}/room-types/{room_id}/availability",
            params={"req_check_in": check_in, "req_check_out": check_out},
        )
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    async def test_hotel_not_found(self, client, hotel_and_room):
        _, room_id = hotel_and_room
        resp = await client.get(
            f"/api/v1/hotels/999999/room-types/{room_id}/availability",
            params=self._dates(),
        )
        assert resp.status_code == 404

    async def test_room_type_not_found(self, client, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.get(
            f"/api/v1/hotels/{hotel_id}/room-types/999999/availability",
            params=self._dates(),
        )
        assert resp.status_code == 404
