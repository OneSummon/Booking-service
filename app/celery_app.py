from datetime import timedelta
import logging
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart

from celery.schedules import crontab
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import selectinload
from app.database.database import async_session
from app.config import settings
from email.mime.text import MIMEText
from celery import Celery

from app.schemas.enums import BookingStatus, PaymentStatus
from app.database.models import Booking, RefreshToken, RoomType
from app.templates import template_checkin_reminder_text, template_checkin_reminder_html
from app.utils import utcnow
from app.yookassa_config import yookassa_cancel_payment, yookassa_init

logger = logging.getLogger(__name__)

celery = Celery(
    "celery_app",
    broker=settings.tasks_storage
)


celery.conf.beat_schedule = {
    "cancel-pending-bookings": {
        "task": "app.celery_app.cancel_pending_bookings",
        "schedule": timedelta(minutes=settings.ttl_pending_bookings),
    },
    "complete-finished-bookings": {
        "task": "app.celery_app.complete_finished_bookings",
        "schedule": crontab(hour=0, minute=0),
    },
    "clean-refresh-tokens": {
        "task": "app.celery_app.clean_refresh_tokens",
        "schedule": crontab(hour=1, minute=0),
    },
    "send-checkin-reminders": {
        "task": "app.celery_app.send_checkin_reminders",
        "schedule": crontab(hour=10, minute=0)
    },
}


@celery.task
def send_email(to: str, subject: str, body_plain: str, body_html: str):
    message = MIMEMultipart("alternative")
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject

    message.attach(MIMEText(body_plain, "plain"))
    message.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(settings.mail_server, settings.mail_port) as server:
        server.login(settings.mail_username, settings.mail_password)
        server.send_message(message)


@celery.task
def cancel_pending_bookings():
    asyncio.run(_cancel_pending_bookings())

async def _cancel_pending_bookings():
    yookassa_init()
    now = utcnow()
    cutoff = now - timedelta(minutes=settings.ttl_pending_bookings)

    async with async_session() as session:
        overdue = await session.scalars(
            select(Booking)
            .where(
                Booking.status == BookingStatus.pending,
                Booking.created_at < cutoff
            )
            .options(selectinload(Booking.payment))
            .with_for_update(skip_locked=True)
        )

        booking_ids = []
        for booking in overdue.all():
            booking_ids.append(booking.id)
            if (
                booking.payment
                and booking.payment.provider_tx_id
                and booking.payment.status == PaymentStatus.pending
            ):
                booking.payment.status = PaymentStatus.cancelled
                try:
                    await yookassa_cancel_payment(booking.payment.provider_tx_id)
                except Exception:
                    logger.warning(f"Не удалось отменить платёж YooKassa при авто-отмене, booking_id: {booking.id}")

        if booking_ids:
            await session.execute(
                update(Booking)
                .where(Booking.id.in_(booking_ids))
                .values(
                    status=BookingStatus.cancelled,
                    cancelled_at=now,
                    cancellation_reason="Payment for booking is overdue"
                )
            )
        await session.commit()


@celery.task
def complete_finished_bookings():
    asyncio.run(_complete_finished_bookings())

async def _complete_finished_bookings():
    now = utcnow()
    async with async_session() as session:
        await session.execute(update(Booking).where(
            Booking.status == BookingStatus.confirmed,
            Booking.check_out < now
        ).values(
            status=BookingStatus.completed
        ))
        await session.commit()


@celery.task
def clean_refresh_tokens():
    asyncio.run(_clean_refresh_tokens())

async def _clean_refresh_tokens():
    now = utcnow()
    async with async_session() as session:
        await session.execute(delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < now,
                RefreshToken.revoked_at.is_not(None)
            )
        ))
        await session.commit()


@celery.task
def send_checkin_reminders():
    asyncio.run(_send_checkin_reminders())

async def _send_checkin_reminders():
    now = utcnow()
    async with async_session() as session:
        upcoming_bookings = await session.scalars(select(Booking).where(
            Booking.status == BookingStatus.confirmed,
            Booking.check_in >= now + timedelta(hours=24),
            Booking.check_in < now + timedelta(hours=48)
        ).options(
            selectinload(Booking.user),
            selectinload(Booking.room_type).selectinload(RoomType.hotel)
        ))

        for upc_booking in upcoming_bookings.all():
            fmt_check_in = upc_booking.check_in.strftime("%d.%m.%Y")
            fmt_check_out = upc_booking.check_out.strftime("%d.%m.%Y")
            send_email.delay(
                to=upc_booking.user.email,
                subject="Ваш заезд через 24 часа!",
                body_plain=template_checkin_reminder_text.format(
                    booking_id=upc_booking.id,
                    hotel_name=upc_booking.room_type.hotel.name,
                    room_type_name=upc_booking.room_type.name,
                    check_in=fmt_check_in,
                    check_out=fmt_check_out,
                    guests_count=upc_booking.guests_count
                ),
                body_html=template_checkin_reminder_html.format(
                    booking_id=upc_booking.id,
                    hotel_name=upc_booking.room_type.hotel.name,
                    room_type_name=upc_booking.room_type.name,
                    check_in=fmt_check_in,
                    check_out=fmt_check_out,
                    guests_count=upc_booking.guests_count
                )
            )