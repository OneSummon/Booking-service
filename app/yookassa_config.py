import uuid
import asyncio
from app.database.models import Booking
from app.config import settings
from fastapi import HTTPException, status
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotificationFactory
from yookassa.domain.common import SecurityHelper

def yookassa_init():
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key

def create_payment(booking: Booking):
    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        "amount": {
            "value": f"{booking.total_price:.2f}",
            "currency": "RUB"
        },
        "payment_method_data": {
            "type": "bank_card"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": settings.return_url
        },
        "description": f"Заказ №{booking.id}",
        "capture": True
    }, idempotence_key)

    return {
        "provider_tx_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url
    }

async def yookassa_create_payment(booking: Booking):
    yookassa_payment = await asyncio.to_thread(create_payment, booking)
    return yookassa_payment

def get_notification(body: dict):
    notification = WebhookNotificationFactory().create(body)
    event = notification.event
    payment_id = notification.object.id

    return event, payment_id

async def thread_get_notification(body: dict):
    notification = await asyncio.to_thread(get_notification, body)
    return notification

def is_yookassa(ip: str):
    if not SecurityHelper().is_ip_trusted(ip):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP does not belong to YooKassa")


def _check_payment_status(payment_id: str) -> str:
    return Payment.find_one(payment_id).status


async def yookassa_check_payment_status(payment_id: str) -> str:
    return await asyncio.to_thread(_check_payment_status, payment_id)


def _cancel_yookassa_payment(payment_id: str) -> None:
    Payment.cancel(payment_id, str(uuid.uuid4()))


async def yookassa_cancel_payment(payment_id: str) -> None:
    await asyncio.to_thread(_cancel_yookassa_payment, payment_id)
