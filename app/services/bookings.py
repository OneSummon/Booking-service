from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.celery_app import send_email
from app.database.models import Booking, RoomType
from app.schemas.bookings import BookingFilterSchema
from app.schemas.enums import BookingStatus
from app.templates import template_create_booking_text, template_create_booking_html
from app.utils import utcnow


async def set_booking(
    room_type_id: int,
    check_in: datetime,
    check_out: datetime,
    guests_count: int,
    total_price: Decimal,
    user_id: int,
    email: str,
    hotel_name: str,
    room_type_name: str,
    nights_count: int,
    session: AsyncSession
):
    new_booking = Booking(
        user_id=user_id,
        room_type_id=room_type_id,
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
        total_price=total_price
    )
    session.add(new_booking)
    await session.flush()

    fmt_check_in = check_in.strftime("%d.%m.%Y")
    fmt_check_out = check_out.strftime("%d.%m.%Y")

    send_email.delay(
        to=email,
        subject="Бронь успешно создана",
        body_plain=template_create_booking_text.format(
            booking_id=new_booking.id,
            hotel_name=hotel_name,
            room_type_name=room_type_name,
            check_in=fmt_check_in,
            check_out=fmt_check_out,
            guests_count=guests_count,
            nights_count=nights_count,
            total_price=total_price
        ),
        body_html=template_create_booking_html.format(
            booking_id=new_booking.id,
            hotel_name=hotel_name,
            room_type_name=room_type_name,
            check_in=fmt_check_in,
            check_out=fmt_check_out,
            guests_count=guests_count,
            nights_count=nights_count,
            total_price=total_price
        )
    )

    return new_booking


async def get_user_bookings(
    filters: BookingFilterSchema,
    user_id: int,
    session: AsyncSession
    ):
    request = select(Booking).where(Booking.user_id == user_id)

    if filters.room_type_id is not None:
        request = request.where(Booking.room_type_id == filters.room_type_id)

    if filters.check_in is not None:
        request = request.where(Booking.check_in >= filters.check_in)

    if filters.check_out is not None:
        request = request.where(Booking.check_out <= filters.check_out)

    if filters.guests_count is not None:
        request = request.where(Booking.guests_count == filters.guests_count)

    if filters.min_price is not None:
        request = request.where(Booking.total_price >= filters.min_price)

    if filters.max_price is not None:
        request = request.where(Booking.total_price <= filters.max_price)

    if filters.status is not None:
        request = request.where(Booking.status == filters.status)

    if filters.created_from is not None:
        request = request.where(Booking.created_at >= filters.created_from)

    if filters.created_to is not None:
        request = request.where(Booking.created_at <= filters.created_to)

    request = request.order_by(Booking.created_at.desc()).offset(filters.offset).limit(filters.limit)

    bookings_list = await session.scalars(request)
    return bookings_list.all()


async def get_booking(booking_id: int, session: AsyncSession):
    return await session.scalar(select(Booking).where(Booking.id == booking_id))


async def get_booking_with_relations(booking_id: int, session: AsyncSession):
    return await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.user),
            selectinload(Booking.room_type).selectinload(RoomType.hotel)
        )
    )


async def get_booking_with_lock(booking_id: int, session: AsyncSession):
    return await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())


async def get_all_bookings(session: AsyncSession, offset: int = 0, limit: int = 50):
    all_bookings = await session.scalars(
        select(Booking).order_by(Booking.created_at.desc()).offset(offset).limit(limit)
    )
    return all_bookings.all()


async def cancellation(booking: Booking, session: AsyncSession, cancellation_reason: str | None = None):
    booking.status = BookingStatus.cancelled
    booking.cancelled_at = utcnow()

    if cancellation_reason is not None:
        booking.cancellation_reason = cancellation_reason
