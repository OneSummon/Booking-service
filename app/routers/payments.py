import logging
from app.limiter import limiter
from app.config import settings
from fastapi import APIRouter, HTTPException, Request, status
from app.schemas.enums import BookingStatus, PaymentStatus
from app.schemas.payments import CheckoutResponseSchema, PaymentInfoSchema
from app.services.bookings import get_booking, get_booking_with_lock
from app.services.payment import get_payment, get_payment_with_lock, set_payment, update_statuses
from app.security import get_real_ip
from app.session_dep import SessionDep
from app.dependencies import CurrentUserDep
from app.yookassa_config import is_yookassa, thread_get_notification, yookassa_create_payment, yookassa_check_payment_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/checkout/{booking_id}", response_model=CheckoutResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_payment(request: Request, booking_id: int, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Начало создания платежа, booking_id: {booking_id}, user_id: {current_user.id}")
    exst_booking = await get_booking_with_lock(booking_id, session)
    if exst_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if exst_booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't get someone else's booking")

    if exst_booking.status == BookingStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pay for a cancelled booking")

    if exst_booking.status == BookingStatus.confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking has already been paid")

    if exst_booking.payment is not None:
        if exst_booking.payment.status != PaymentStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A payment for this booking has already been created")

        if exst_booking.payment.provider_tx_id is not None:
            yk_status = await yookassa_check_payment_status(exst_booking.payment.provider_tx_id)
            if yk_status not in ("canceled", "expired"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A payment is already in progress")

        await session.delete(exst_booking.payment)
        await session.flush()
        logger.debug(f"Просроченный платёж отменён, booking_id: {booking_id}")

    yookassa_payment = await yookassa_create_payment(exst_booking)
    await set_payment(exst_booking, yookassa_payment["provider_tx_id"], session)

    logger.debug(f"Платёж создан, booking_id: {booking_id}, user_id: {current_user.id}")
    return {"confirmation_url": yookassa_payment["confirmation_url"]}


@router.get("/{booking_id}", response_model=PaymentInfoSchema, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def get_payment_info(request: Request, booking_id: int, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Запрос статуса платежа, booking_id: {booking_id}, user_id: {current_user.id}")
    exst_booking = await get_booking(booking_id, session)
    if exst_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if exst_booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't get someone else's payment")

    if exst_booking.payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return exst_booking.payment


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("100/minute")
async def webhook(request: Request, session: SessionDep):
    ip = get_real_ip(request)
    logger.debug(f"Получен webhook, ip: {ip}")

    if settings.verify_webhook_ip:
        is_yookassa(ip)

    try:
        body = await request.json()
        event, payment_id = await thread_get_notification(body)
    except Exception:
        logger.warning(f"Не удалось распарсить тело webhook, ip: {ip}")
        return
    logger.debug(f"Webhook событие: {event}, payment_id: {payment_id}")

    payment = await get_payment_with_lock(payment_id, session)
    if payment is None:
        logger.warning(f"Платёж не найден, payment_id: {payment_id}")
        return

    await update_statuses(event, payment.booking_id, payment, session)
    logger.debug(f"Статусы обновлены, booking_id: {payment.booking_id}, event: {event}")
