import logging
from datetime import timezone

from app.limiter import limiter
from fastapi import APIRouter, HTTPException, Depends, Request, status
from app.schemas.bookings import BookingFilterSchema, CancelBookingSchema, CreateBookingSchema, InfoBookingSchema
from app.schemas.enums import BookingStatus, PaymentStatus
from app.services.bookings import cancellation, get_booking, get_booking_with_lock, get_user_bookings, set_booking
from app.services.hotels import acquire_room_booking_lock, get_count_booked_rooms, get_hotel_by_id, get_room_type_with_block
from app.dependencies import CurrentUserDep
from app.session_dep import SessionDep
from app.utils import utcnow
from app.yookassa_config import yookassa_cancel_payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=InfoBookingSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_booking(
    request: Request,
    data: CreateBookingSchema,
    current_user: CurrentUserDep,
    session: SessionDep
    ):
    logger.debug("Начало создания бронирования")
    check_in_utc = data.check_in.astimezone(timezone.utc).replace(tzinfo=None) if data.check_in.tzinfo else data.check_in
    check_out_utc = data.check_out.astimezone(timezone.utc).replace(tzinfo=None) if data.check_out.tzinfo else data.check_out

    if check_in_utc >= check_out_utc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="check_in must be before check_out")

    if check_in_utc.date() < utcnow().date():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="check_in can't be in the past")

    await acquire_room_booking_lock(data.room_type_id, session)
    exst_room_type = await get_room_type_with_block(data.room_type_id, session)
    if exst_room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    exst_hotel = await get_hotel_by_id(exst_room_type.hotel_id, session)
    if exst_hotel is None or not exst_hotel.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    booked_count = await get_count_booked_rooms(
        data.room_type_id,
        check_in_utc,
        check_out_utc,
        session
    )
    available = exst_room_type.total_rooms - booked_count
    if available <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There are no rooms available for this range")

    if exst_room_type.capacity < data.guests_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="guests_count can't be more than capacity")

    nights_count = (check_out_utc.date() - check_in_utc.date()).days
    if nights_count <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="check_out must be at least one day after check_in")
    total_price = nights_count * exst_room_type.price_per_night

    new_booking = await set_booking(
        data.room_type_id,
        check_in_utc,
        check_out_utc,
        data.guests_count,
        total_price,
        current_user.id,
        current_user.email,
        exst_hotel.name,
        exst_room_type.name,
        nights_count,
        session
    )
    logger.debug(f"Бронирование создано, id: {new_booking.id}, user_id: {current_user.id}")
    return new_booking


@router.get("", response_model=list[InfoBookingSchema], status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def my_bookings(request: Request, current_user: CurrentUserDep, session: SessionDep, filters: BookingFilterSchema = Depends()):
    logger.debug(f"Запрос списка бронирований, user_id: {current_user.id}")
    my_bookings_list = await get_user_bookings(filters, current_user.id, session)
    return my_bookings_list


@router.get("/{booking_id}", response_model=InfoBookingSchema, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def get_specific_booking(request: Request, booking_id: int, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Запрос бронирования, id: {booking_id}, user_id: {current_user.id}")
    exst_booking = await get_booking(booking_id, session)

    if exst_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != exst_booking.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot get someone else's booking")

    return exst_booking


@router.post("/{booking_id}/cancel", response_model=InfoBookingSchema, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def cancel(
    request: Request,
    booking_id: int,
    data: CancelBookingSchema,
    current_user: CurrentUserDep,
    session: SessionDep,
    ):
    logger.debug(f"Начало отмены бронирования, id: {booking_id}, user_id: {current_user.id}")
    exst_booking = await get_booking_with_lock(booking_id, session)

    if exst_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.id != exst_booking.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't cancel someone else's booking")

    if exst_booking.status == BookingStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot cancel a completed booking")

    if exst_booking.cancelled_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking has already been cancelled")

    await cancellation(exst_booking, session, data.cancellation_reason)

    if exst_booking.payment and exst_booking.payment.provider_tx_id and exst_booking.payment.status == PaymentStatus.pending:
        exst_booking.payment.status = PaymentStatus.cancelled
        try:
            await yookassa_cancel_payment(exst_booking.payment.provider_tx_id)
        except Exception:
            logger.warning(f"Не удалось отменить платёж в YooKassa, booking_id: {booking_id}")

    logger.debug(f"Бронирование отменено, id: {booking_id}, user_id: {current_user.id}")
    return exst_booking
