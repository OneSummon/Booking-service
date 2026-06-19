from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Booking, Payment
from app.schemas.enums import PaymentStatus, BookingStatus
from app.services.bookings import get_booking, get_booking_with_relations
from app.celery_app import send_email
from app.templates import template_confirmed_booking_text, template_confirmed_booking_html
from app.utils import utcnow


async def set_payment(booking: Booking, provider_tx_id: str, session: AsyncSession):
    new_payment = Payment(
        booking_id=booking.id,
        amount=booking.total_price,
        currency="RUB",
        status=PaymentStatus.pending,
        provider_tx_id=provider_tx_id
    )
    session.add(new_payment)
    await session.flush()

    return new_payment


async def get_payment(payment_id: str, session: AsyncSession):
    return await session.scalar(select(Payment).where(Payment.provider_tx_id == payment_id))


async def get_payment_with_lock(payment_id: str, session: AsyncSession):
    return await session.scalar(
        select(Payment).where(Payment.provider_tx_id == payment_id).with_for_update()
    )


async def update_statuses(event: str, booking_id: int, payment: Payment, session: AsyncSession):
    booking = await get_booking(booking_id, session)

    if event == "payment.succeeded":
        if payment.status == PaymentStatus.succeeded:
            return
        if booking is None or booking.status == BookingStatus.cancelled:
            return
        payment.status = PaymentStatus.succeeded
        payment.paid_at = utcnow()
        booking.status = BookingStatus.confirmed

        booking_full = await get_booking_with_relations(booking_id, session)
        nights_count = (booking_full.check_out.date() - booking_full.check_in.date()).days
        fmt_check_in = booking_full.check_in.strftime("%d.%m.%Y")
        fmt_check_out = booking_full.check_out.strftime("%d.%m.%Y")

        send_email.delay(
            to=booking_full.user.email,
            subject="Бронирование подтверждено",
            body_plain=template_confirmed_booking_text.format(
                booking_id=booking_full.id,
                hotel_name=booking_full.room_type.hotel.name,
                room_type_name=booking_full.room_type.name,
                check_in=fmt_check_in,
                check_out=fmt_check_out,
                guests_count=booking_full.guests_count,
                nights_count=nights_count,
                total_price=booking_full.total_price
            ),
            body_html=template_confirmed_booking_html.format(
                booking_id=booking_full.id,
                hotel_name=booking_full.room_type.hotel.name,
                room_type_name=booking_full.room_type.name,
                check_in=fmt_check_in,
                check_out=fmt_check_out,
                guests_count=booking_full.guests_count,
                nights_count=nights_count,
                total_price=booking_full.total_price
            )
        )

    elif event == "payment.canceled":
        payment.status = PaymentStatus.cancelled

    else:
        return
