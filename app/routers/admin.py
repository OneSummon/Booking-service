import logging

from fastapi_cache import FastAPICache
from app.limiter import limiter
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from app.schemas.bookings import CancelBookingSchema, InfoBookingSchema
from app.schemas.enums import BookingStatus, PaymentStatus
from app.schemas.hotels import CreateHotelSchema, CreateRoomTypeSchema, InfoHotelSchema, RoomTypeSchema, UpdateHotelSchema, UpdateRoomTypeSchema
from app.services.bookings import cancellation, get_all_bookings, get_booking, get_booking_with_lock
from app.services.hotels import get_hotel, get_hotel_by_id, get_roomtype_id_with_hotel, hide_hotel, set_hotel, set_room_type, update_hotel, update_room_type
from app.dependencies import CurrentUserDep
from app.security import verify_user_is_admin
from app.session_dep import SessionDep
from app.yookassa_config import yookassa_cancel_payment


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/hotels", response_model=InfoHotelSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def admin_set_hotel(request: Request, data: CreateHotelSchema, current_user: CurrentUserDep, session: SessionDep):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало создания отеля, admin_id: {current_user.id}")

    exst_hotel = await get_hotel(data.name, data.country, data.city, data.address, session)
    if exst_hotel is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hotel already exists")

    try:
        new_hotel = await set_hotel(data, session)
        await FastAPICache.clear()

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hotel already exists")

    logger.debug(f"Отель создан, id: {new_hotel.id}, admin_id: {current_user.id}")
    return new_hotel


@router.patch("/hotels/{hotel_id}", response_model=InfoHotelSchema, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def admin_update_hotel(
    request: Request,
    hotel_id: int,
    data: UpdateHotelSchema,
    current_user: CurrentUserDep,
    session: SessionDep
    ):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало обновления отеля, id: {hotel_id}, admin_id: {current_user.id}")

    exst_hotel = await get_hotel_by_id(hotel_id, session)
    if exst_hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    try:
        updated_hotel = await update_hotel(data, exst_hotel, session)
        await FastAPICache.clear()

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please try again")

    logger.debug(f"Отель обновлён, id: {hotel_id}, admin_id: {current_user.id}")
    return updated_hotel


@router.delete("/hotels/{hotel_id}", response_model=InfoHotelSchema, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def admin_hide_hotel(request: Request, hotel_id: int, current_user: CurrentUserDep, session: SessionDep):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало скрытия отеля, id: {hotel_id}, admin_id: {current_user.id}")

    exst_hotel = await get_hotel_by_id(hotel_id, session)
    if exst_hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    await hide_hotel(exst_hotel, session)
    await FastAPICache.clear()

    logger.debug(f"Отель скрыт, id: {hotel_id}, admin_id: {current_user.id}")
    return exst_hotel


@router.post("/hotels/{hotel_id}/room-types", response_model=RoomTypeSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def admin_set_room_type(
    request: Request,
    hotel_id: int,
    data: CreateRoomTypeSchema,
    current_user: CurrentUserDep,
    session: SessionDep
    ):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало создания типа номера, hotel_id: {hotel_id}, admin_id: {current_user.id}")

    exst_hotel = await get_hotel_by_id(hotel_id, session)
    if exst_hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    try:
        new_room_type = await set_room_type(data, hotel_id, session)
        await FastAPICache.clear()

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please try again")

    logger.debug(f"Тип номера создан, id: {new_room_type.id}, hotel_id: {hotel_id}, admin_id: {current_user.id}")
    return new_room_type


@router.patch("/hotels/{hotel_id}/room-types/{room_type_id}", response_model=RoomTypeSchema, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def admin_update_room_type(
    request: Request,
    hotel_id: int,
    room_type_id: int,
    data: UpdateRoomTypeSchema,
    current_user: CurrentUserDep,
    session: SessionDep
    ):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало обновления типа номера, id: {room_type_id}, admin_id: {current_user.id}")

    exst_room_type = await get_roomtype_id_with_hotel(room_type_id, hotel_id, session)
    if exst_room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room type or hotel not found")

    try:
        await update_room_type(data, exst_room_type, session)
        await FastAPICache.clear()

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please try again")

    logger.debug(f"Тип номера обновлён, id: {room_type_id}, admin_id: {current_user.id}")
    return exst_room_type


@router.get("/bookings", response_model=list[InfoBookingSchema], status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def admin_get_all_bookings(
    request: Request,
    current_user: CurrentUserDep,
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000)
    ):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Запрос всех бронирований, admin_id: {current_user.id}")

    all_bookings_list = await get_all_bookings(session, offset=offset, limit=limit)
    return all_bookings_list


@router.patch("/bookings/{booking_id}/cancel", response_model=InfoBookingSchema, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def admin_cancel_booking(
    request: Request,
    booking_id: int,
    data: CancelBookingSchema,
    current_user: CurrentUserDep,
    session: SessionDep
    ):
    verify_user_is_admin(current_user.role)
    logger.debug(f"Начало отмены бронирования (admin), id: {booking_id}, admin_id: {current_user.id}")

    exst_booking = await get_booking_with_lock(booking_id, session)

    if exst_booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

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
            logger.warning(f"Не удалось отменить платёж в YooKassa (admin), booking_id: {booking_id}")

    logger.debug(f"Бронирование отменено (admin), id: {booking_id}, admin_id: {current_user.id}")
    return exst_booking
