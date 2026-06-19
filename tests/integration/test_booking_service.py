from datetime import timedelta
from decimal import Decimal

import pytest

from app.database.models import Hotel, RoomType, User
from app.schemas.bookings import BookingFilterSchema
from app.schemas.enums import BookingStatus, UserStatus
from app.security import hash_obj
from app.services.bookings import (
    cancellation,
    get_all_bookings,
    get_booking,
    get_user_bookings,
    set_booking,
)
from app.utils import utcnow


@pytest.fixture
async def db_user(session):
    u = User(email="booker@test.com", password_hash=hash_obj("pass123"), role=UserStatus.user)
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def room_type(session):
    hotel = Hotel(
        name="Test Hotel", city="Moscow", country="Russia",
        star_rating=4.0, description="x", address="y",
    )
    session.add(hotel)
    await session.flush()
    rt = RoomType(
        hotel_id=hotel.id, name="Standard", capacity=2,
        bed_type="double", price_per_night=Decimal("100.00"), total_rooms=5,
    )
    session.add(rt)
    await session.flush()
    return rt


async def _make_booking(session, db_user, room_type, days_ahead=10, duration=2):
    check_in = utcnow() + timedelta(days=days_ahead)
    check_out = check_in + timedelta(days=duration)
    return await set_booking(
        room_type_id=room_type.id,
        check_in=check_in,
        check_out=check_out,
        guests_count=1,
        total_price=Decimal("200.00"),
        user_id=db_user.id,
        email=db_user.email,
        hotel_name="Test Hotel",
        room_type_name="Standard",
        nights_count=duration,
        session=session,
    )


@pytest.fixture
async def booking(session, db_user, room_type):
    return await _make_booking(session, db_user, room_type)


class TestSetBooking:
    async def test_creates_record_with_pending_status(self, session, db_user, room_type):
        b = await _make_booking(session, db_user, room_type)
        assert b.id is not None
        assert b.status == BookingStatus.pending

    async def test_stores_total_price(self, session, db_user, room_type):
        b = await _make_booking(session, db_user, room_type)
        assert b.total_price == Decimal("200.00")

    async def test_calls_send_email_delay(self, session, db_user, room_type, mock_send_email):
        await _make_booking(session, db_user, room_type)
        mock_send_email.assert_called_once()

    async def test_email_sent_to_correct_address(self, session, db_user, room_type, mock_send_email):
        await _make_booking(session, db_user, room_type)
        call_kwargs = mock_send_email.call_args.kwargs
        assert call_kwargs["to"] == db_user.email


class TestGetBooking:
    async def test_returns_existing_booking(self, session, booking):
        found = await get_booking(booking.id, session)
        assert found is not None
        assert found.id == booking.id

    async def test_returns_none_for_nonexistent(self, session):
        assert await get_booking(999999, session) is None


class TestGetUserBookings:
    async def test_returns_only_that_users_bookings(self, session, db_user, booking):
        other_user = User(
            email="other@test.com", password_hash=hash_obj("pass"), role=UserStatus.user
        )
        session.add(other_user)
        await session.flush()

        filters = BookingFilterSchema()
        bookings = await get_user_bookings(filters, db_user.id, session)
        assert all(b.user_id == db_user.id for b in bookings)

    async def test_filters_by_status_match(self, session, db_user, booking):
        filters = BookingFilterSchema(status=BookingStatus.pending)
        bookings = await get_user_bookings(filters, db_user.id, session)
        assert len(bookings) >= 1
        assert all(b.status == BookingStatus.pending for b in bookings)

    async def test_filters_by_status_no_match(self, session, db_user, booking):
        filters = BookingFilterSchema(status=BookingStatus.confirmed)
        bookings = await get_user_bookings(filters, db_user.id, session)
        assert len(bookings) == 0

    async def test_ordered_by_created_at_desc(self, session, db_user, room_type):
        for days in (5, 15, 25):
            await _make_booking(session, db_user, room_type, days_ahead=days)

        filters = BookingFilterSchema()
        bookings = await get_user_bookings(filters, db_user.id, session)
        dates = [b.created_at for b in bookings]
        assert dates == sorted(dates, reverse=True)


class TestGetAllBookings:
    async def test_returns_all_bookings(self, session, booking):
        all_b = await get_all_bookings(session)
        assert len(all_b) >= 1

    async def test_ordered_by_created_at_desc(self, session, db_user, room_type):
        for days in (5, 10, 15):
            await _make_booking(session, db_user, room_type, days_ahead=days)

        all_b = await get_all_bookings(session)
        dates = [b.created_at for b in all_b]
        assert dates == sorted(dates, reverse=True)

    async def test_respects_limit(self, session, db_user, room_type):
        for days in range(5, 25, 2):
            await _make_booking(session, db_user, room_type, days_ahead=days)

        all_b = await get_all_bookings(session, limit=3)
        assert len(all_b) <= 3


class TestCancellation:
    async def test_sets_status_to_cancelled(self, session, booking):
        await cancellation(booking, session)
        assert booking.status == BookingStatus.cancelled

    async def test_sets_cancelled_at_timestamp(self, session, booking):
        before = utcnow()
        await cancellation(booking, session)
        assert booking.cancelled_at is not None
        assert booking.cancelled_at >= before

    async def test_stores_cancellation_reason(self, session, booking):
        await cancellation(booking, session, "Changed plans")
        assert booking.cancellation_reason == "Changed plans"

    async def test_reason_is_none_when_not_provided(self, session, booking):
        await cancellation(booking, session)
        assert booking.cancellation_reason is None
