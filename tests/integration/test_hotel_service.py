from datetime import timedelta
from decimal import Decimal

import pytest

from app.database.models import Booking, Hotel, RoomType, User
from app.schemas.enums import BookingStatus, UserStatus
from app.schemas.hotels import (
    CreateHotelSchema,
    CreateRoomTypeSchema,
    HotelFiltersSchema,
    UpdateHotelSchema,
)
from app.security import hash_obj
from app.services.hotels import (
    acquire_room_booking_lock,
    get_count_booked_rooms,
    get_hotels,
    get_info_hotel,
    get_room_type,
    get_roomtype_id_with_hotel,
    hide_hotel,
    set_hotel,
    set_room_type,
    update_hotel,
)
from app.utils import utcnow


def _hotel_schema(**kwargs):
    return CreateHotelSchema(**{
        "name": "Grand Hotel",
        "city": "Moscow",
        "country": "Russia",
        "star_rating": 4.0,
        "description": "A fine hotel",
        "address": "1 Red Square",
        **kwargs,
    })


def _room_schema(**kwargs):
    return CreateRoomTypeSchema(**{
        "name": "Standard",
        "capacity": 2,
        "bed_type": "double",
        "price_per_night": Decimal("120.00"),
        "total_rooms": 10,
        **kwargs,
    })


@pytest.fixture
async def hotel(session):
    return await set_hotel(_hotel_schema(), session)


@pytest.fixture
async def room_type(session, hotel):
    return await set_room_type(_room_schema(), hotel.id, session)


@pytest.fixture
async def db_user(session):
    u = User(email="tester@test.com", password_hash=hash_obj("pass"), role=UserStatus.user)
    session.add(u)
    await session.flush()
    return u


class TestSetHotel:
    async def test_creates_hotel(self, session):
        h = await set_hotel(_hotel_schema(), session)
        assert h.id is not None
        assert h.name == "Grand Hotel"

    async def test_is_active_by_default(self, session):
        h = await set_hotel(_hotel_schema(), session)
        assert h.is_active is True

    async def test_stores_all_fields(self, session):
        h = await set_hotel(_hotel_schema(city="SPb", star_rating=5.0), session)
        assert h.city == "SPb"
        assert h.star_rating == 5.0


class TestGetHotels:
    async def test_returns_active_hotels(self, session, hotel):
        hotels = await get_hotels(HotelFiltersSchema(), session)
        assert any(h.id == hotel.id for h in hotels)

    async def test_excludes_inactive_hotels(self, session, hotel):
        await hide_hotel(hotel, session)
        hotels = await get_hotels(HotelFiltersSchema(), session)
        assert all(h.is_active for h in hotels)
        assert not any(h.id == hotel.id for h in hotels)

    async def test_filters_by_city(self, session, hotel):
        hotels = await get_hotels(HotelFiltersSchema(city="Moscow"), session)
        assert all("moscow" in h.city.lower() for h in hotels)

    async def test_filters_by_min_star_rating(self, session, hotel):
        hotels = await get_hotels(HotelFiltersSchema(min_star_rating=4.0), session)
        assert all(h.star_rating >= 4.0 for h in hotels)

    async def test_city_filter_no_match(self, session, hotel):
        hotels = await get_hotels(HotelFiltersSchema(city="Berlin"), session)
        assert not any(h.id == hotel.id for h in hotels)


class TestGetInfoHotel:
    async def test_returns_active_hotel(self, session, hotel):
        found = await get_info_hotel(hotel.id, session)
        assert found is not None
        assert found.id == hotel.id

    async def test_returns_none_for_inactive(self, session, hotel):
        await hide_hotel(hotel, session)
        assert await get_info_hotel(hotel.id, session) is None

    async def test_returns_none_for_nonexistent(self, session):
        assert await get_info_hotel(999999, session) is None


class TestHideHotel:
    async def test_sets_is_active_false(self, session, hotel):
        await hide_hotel(hotel, session)
        assert hotel.is_active is False


class TestUpdateHotel:
    async def test_updates_name(self, session, hotel):
        await update_hotel(UpdateHotelSchema(name="Updated"), hotel, session)
        assert hotel.name == "Updated"

    async def test_partial_update_leaves_other_fields(self, session, hotel):
        original_city = hotel.city
        await update_hotel(UpdateHotelSchema(star_rating=5.0), hotel, session)
        assert hotel.star_rating == 5.0
        assert hotel.city == original_city

    async def test_activates_inactive_hotel(self, session, hotel):
        await hide_hotel(hotel, session)
        await update_hotel(UpdateHotelSchema(is_active=True), hotel, session)
        assert hotel.is_active is True


class TestSetRoomType:
    async def test_creates_room_type(self, session, hotel):
        rt = await set_room_type(_room_schema(), hotel.id, session)
        assert rt.id is not None
        assert rt.hotel_id == hotel.id

    async def test_stores_price_correctly(self, session, hotel):
        rt = await set_room_type(_room_schema(price_per_night=Decimal("250.50")), hotel.id, session)
        assert rt.price_per_night == Decimal("250.50")

    async def test_stores_bed_type(self, session, hotel):
        rt = await set_room_type(_room_schema(bed_type="king"), hotel.id, session)
        assert rt.bed_type == "king"


class TestGetRoomtype:
    async def test_finds_existing(self, session, room_type, hotel):
        found = await get_roomtype_id_with_hotel(room_type.id, hotel.id, session)
        assert found is not None
        assert found.id == room_type.id

    async def test_wrong_hotel_returns_none(self, session, room_type):
        found = await get_roomtype_id_with_hotel(room_type.id, 999999, session)
        assert found is None

    async def test_nonexistent_room_type(self, session, hotel):
        found = await get_roomtype_id_with_hotel(999999, hotel.id, session)
        assert found is None


class TestGetCountBookedRooms:
    async def test_zero_when_no_bookings(self, session, room_type):
        check_in = utcnow() + timedelta(days=10)
        check_out = utcnow() + timedelta(days=12)
        count = await get_count_booked_rooms(room_type.id, check_in, check_out, session)
        assert count == 0

    async def test_counts_overlapping_confirmed_booking(self, session, room_type, db_user):
        check_in = utcnow() + timedelta(days=10)
        check_out = utcnow() + timedelta(days=12)
        booking = Booking(
            user_id=db_user.id,
            room_type_id=room_type.id,
            check_in=check_in,
            check_out=check_out,
            guests_count=1,
            total_price=Decimal("240.00"),
            status=BookingStatus.confirmed,
        )
        session.add(booking)
        await session.flush()

        count = await get_count_booked_rooms(room_type.id, check_in, check_out, session)
        assert count == 1

    async def test_does_not_count_cancelled(self, session, room_type, db_user):
        check_in = utcnow() + timedelta(days=20)
        check_out = utcnow() + timedelta(days=22)
        booking = Booking(
            user_id=db_user.id,
            room_type_id=room_type.id,
            check_in=check_in,
            check_out=check_out,
            guests_count=1,
            total_price=Decimal("240.00"),
            status=BookingStatus.cancelled,
        )
        session.add(booking)
        await session.flush()

        count = await get_count_booked_rooms(room_type.id, check_in, check_out, session)
        assert count == 0

    async def test_non_overlapping_range_not_counted(self, session, room_type, db_user):
        booking = Booking(
            user_id=db_user.id,
            room_type_id=room_type.id,
            check_in=utcnow() + timedelta(days=30),
            check_out=utcnow() + timedelta(days=32),
            guests_count=1,
            total_price=Decimal("240.00"),
            status=BookingStatus.confirmed,
        )
        session.add(booking)
        await session.flush()

        count = await get_count_booked_rooms(
            room_type.id,
            utcnow() + timedelta(days=10),
            utcnow() + timedelta(days=12),
            session,
        )
        assert count == 0

    async def test_adjacent_dates_not_overlapping(self, session, room_type, db_user):
        """Checkout on day 12, new check-in on day 12 — must NOT overlap (same-day turnover)."""
        booking = Booking(
            user_id=db_user.id,
            room_type_id=room_type.id,
            check_in=utcnow() + timedelta(days=10),
            check_out=utcnow() + timedelta(days=12),
            guests_count=1,
            total_price=Decimal("240.00"),
            status=BookingStatus.confirmed,
        )
        session.add(booking)
        await session.flush()

        count = await get_count_booked_rooms(
            room_type.id,
            utcnow() + timedelta(days=12),
            utcnow() + timedelta(days=14),
            session,
        )
        assert count == 0


class TestAcquireRoomBookingLock:
    async def test_executes_without_error(self, session, room_type):
        await acquire_room_booking_lock(room_type.id, session)
