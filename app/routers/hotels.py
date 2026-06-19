import logging
from app.limiter import limiter
from fastapi_cache.decorator import cache
from fastapi import APIRouter, HTTPException, Depends, Request, status
from app.schemas.hotels import AvailabilityOutputSchema, ReqDateSchema, HotelDetailSchema, HotelFiltersSchema, InfoHotelSchema, RoomTypeSchema
from app.services.hotels import get_count_booked_rooms, get_hotels, get_info_hotel, get_roomtype_id_with_hotel
from app.session_dep import SessionDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hotels", tags=["Hotels"])


@router.get("", response_model=list[InfoHotelSchema], status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
@cache(expire=300)
async def get_all_hotels(request: Request, session: SessionDep, filters: HotelFiltersSchema = Depends()):
    logger.debug("Запрос списка отелей")
    return await get_hotels(filters, session)


@router.get("/{hotel_id}", response_model=HotelDetailSchema, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
@cache(expire=300)
async def get_hotel_detail(request: Request, hotel_id: int, session: SessionDep):
    logger.debug(f"Запрос информации об отеле, id: {hotel_id}")
    hotel = await get_info_hotel(hotel_id, session)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    return hotel


@router.get("/{hotel_id}/room-types", response_model=list[RoomTypeSchema], status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
@cache(expire=3600)
async def get_list_room_types(request: Request, hotel_id: int, session: SessionDep):
    logger.debug(f"Запрос списка типов номеров, hotel_id: {hotel_id}")
    hotel = await get_info_hotel(hotel_id, session)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    room_types_list = hotel.room_types
    return room_types_list


@router.get("/{hotel_id}/room-types/{room_type_id}/availability", response_model=AvailabilityOutputSchema, status_code=status.HTTP_200_OK)
@limiter.limit("50/minute")
async def availability(
    request: Request,
    hotel_id: int,
    room_type_id: int,
    session: SessionDep,
    data: ReqDateSchema = Depends()
    ):
    logger.debug(f"Запрос доступности номера, room_type_id: {room_type_id}, hotel_id: {hotel_id}")
    hotel = await get_info_hotel(hotel_id, session)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    room_type = await get_roomtype_id_with_hotel(room_type_id, hotel_id, session)
    if room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room type not found")

    booked_count = await get_count_booked_rooms(
        room_type_id,
        data.req_check_in,
        data.req_check_out,
        session
        )
    available = room_type.total_rooms - booked_count
    logger.debug(f"Доступно номеров: {available}, room_type_id: {room_type_id}")

    if available > 0:
        return {
            "available": True,
            "count_available_rooms": available,
            "requested_date": f"{data.req_check_in} - {data.req_check_out}"
        }
    else:
        return {
            "available": False,
            "requested_date": f"{data.req_check_in} - {data.req_check_out}"
        }