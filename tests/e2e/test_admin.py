import pytest


HOTEL_DATA = {
    "name": "Grand Palace", "city": "SPb", "country": "Russia",
    "star_rating": 5.0, "description": "Luxurious", "address": "Palace Square 1",
}
ROOM_DATA = {
    "name": "Junior Suite", "capacity": 3, "bed_type": "king",
    "price_per_night": "250.00", "total_rooms": 5,
}


class TestAdminHotels:
    async def test_create_hotel(self, client, admin_token):
        resp = await client.post(
            "/api/v1/admin/hotels",
            json=HOTEL_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Grand Palace"
        assert body["is_active"] is True

    async def test_create_hotel_duplicate_rejected(self, client, admin_token):
        await client.post(
            "/api/v1/admin/hotels", json=HOTEL_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = await client.post(
            "/api/v1/admin/hotels", json=HOTEL_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    async def test_update_hotel(self, client, admin_token, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.patch(
            f"/api/v1/admin/hotels/{hotel_id}",
            json={"name": "Updated Name", "star_rating": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Updated Name"
        assert body["star_rating"] == 5.0

    async def test_update_hotel_not_found(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/admin/hotels/999999",
            json={"name": "x"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_hide_hotel(self, client, admin_token, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.delete(
            f"/api/v1/admin/hotels/{hotel_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        get_resp = await client.get("/api/v1/hotels")
        ids = [h["id"] for h in get_resp.json()]
        assert hotel_id not in ids

    async def test_user_cannot_create_hotel(self, client, user_token):
        access_token, _ = user_token
        resp = await client.post(
            "/api/v1/admin/hotels",
            json=HOTEL_DATA,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_create_hotel(self, client):
        resp = await client.post("/api/v1/admin/hotels", json=HOTEL_DATA)
        assert resp.status_code == 401


class TestAdminRoomTypes:
    async def test_create_room_type(self, client, admin_token, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.post(
            f"/api/v1/admin/hotels/{hotel_id}/room-types",
            json=ROOM_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Junior Suite"
        assert body["bed_type"] == "king"
        assert body["hotel_id"] == hotel_id

    async def test_create_room_type_hotel_not_found(self, client, admin_token):
        resp = await client.post(
            "/api/v1/admin/hotels/999999/room-types",
            json=ROOM_DATA,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_update_room_type(self, client, admin_token, hotel_and_room):
        hotel_id, room_id = hotel_and_room
        resp = await client.patch(
            f"/api/v1/admin/hotels/{hotel_id}/room-types/{room_id}",
            json={"price_per_night": "150.00", "total_rooms": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["price_per_night"] == "150.00"
        assert body["total_rooms"] == 10

    async def test_update_room_type_not_found(self, client, admin_token, hotel_and_room):
        hotel_id, _ = hotel_and_room
        resp = await client.patch(
            f"/api/v1/admin/hotels/{hotel_id}/room-types/999999",
            json={"price_per_night": "150.00"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_invalid_bed_type_rejected(self, client, admin_token, hotel_and_room):
        hotel_id, _ = hotel_and_room
        bad_room = {**ROOM_DATA, "bed_type": "hammock"}
        resp = await client.post(
            f"/api/v1/admin/hotels/{hotel_id}/room-types",
            json=bad_room,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422


class TestAdminBookings:
    async def test_get_all_bookings(self, client, admin_token, user_booking):
        resp = await client.get(
            "/api/v1/admin/bookings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_all_bookings_pagination(self, client, admin_token, user_booking):
        resp = await client.get(
            "/api/v1/admin/bookings",
            params={"limit": 1, "offset": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    async def test_cancel_booking(self, client, admin_token, user_booking):
        booking_id = user_booking["id"]
        resp = await client.patch(
            f"/api/v1/admin/bookings/{booking_id}/cancel",
            json={"cancellation_reason": "Admin decision"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["cancellation_reason"] == "Admin decision"

    async def test_cancel_already_cancelled_rejected(self, client, admin_token, user_booking):
        booking_id = user_booking["id"]
        await client.patch(
            f"/api/v1/admin/bookings/{booking_id}/cancel",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = await client.patch(
            f"/api/v1/admin/bookings/{booking_id}/cancel",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    async def test_cancel_not_found(self, client, admin_token):
        resp = await client.patch(
            "/api/v1/admin/bookings/999999/cancel",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_user_cannot_view_all_bookings(self, client, user_token):
        access_token, _ = user_token
        resp = await client.get(
            "/api/v1/admin/bookings",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 403
