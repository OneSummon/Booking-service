from datetime import datetime
from app.schemas.enums import BookingStatus
from app.schemas.hotels import CreateHotelSchema, CreateRoomTypeSchema, HotelFiltersSchema, UpdateHotelSchema, UpdateRoomTypeSchema
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Hotel, RoomType, Booking


async def acquire_room_booking_lock(room_type_id: int, session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(room_type_id)))


async def get_hotels(filters: HotelFiltersSchema, session: AsyncSession):
    request = select(Hotel).where(Hotel.is_active.is_(True))

    if filters.name is not None:
        request = request.where(Hotel.name.ilike(f"%{filters.name}%"))

    if filters.city is not None:
        request = request.where(Hotel.city.ilike(f"%{filters.city}%"))

    if filters.country is not None:
        request = request.where(Hotel.country.ilike(f"%{filters.country}%"))

    if filters.min_star_rating is not None:
        request = request.where(Hotel.star_rating >= filters.min_star_rating)

    if filters.max_star_rating is not None:
        request = request.where(Hotel.star_rating <= filters.max_star_rating)

    if filters.address is not None:
        request = request.where(Hotel.address.ilike(f"%{filters.address}%"))

    request = request.offset(filters.offset).limit(filters.limit)

    hotels = await session.scalars(request)
    return hotels.all()


async def get_info_hotel(hotel_id: int, session: AsyncSession):
    return await session.scalar(select(Hotel).where(Hotel.id == hotel_id, Hotel.is_active.is_(True)))


async def get_hotel(name: str, country: str, city: str, address: str, session: AsyncSession):
    return await session.scalar(select(Hotel).where(
        Hotel.name == name,
        Hotel.country == country,
        Hotel.city == city,
        Hotel.address == address,
        Hotel.is_active.is_(True)
        ))


async def get_hotel_by_id(hotel_id: int, session: AsyncSession):
    return await session.scalar(select(Hotel).where(Hotel.id == hotel_id))


async def get_room_type(room_type_id: int, session: AsyncSession):
    return await session.scalar(select(RoomType).where(RoomType.id == room_type_id))


async def get_room_type_with_block(room_type_id: int, session: AsyncSession):
    return await session.scalar(select(RoomType).where(RoomType.id == room_type_id).with_for_update())


async def get_roomtype_id_with_hotel(room_type_id: int, hotel_id: int, session: AsyncSession):
    return await session.scalar(select(RoomType).where(RoomType.id == room_type_id, RoomType.hotel_id == hotel_id))


async def get_count_booked_rooms(
        room_type_id: int,
        req_check_in: datetime,
        req_check_out: datetime,
        session: AsyncSession
        ):
    request = select(func.count()).select_from(Booking).where(
        Booking.room_type_id == room_type_id,
        Booking.check_out > req_check_in,
        Booking.check_in < req_check_out,
        Booking.status.not_in([BookingStatus.cancelled])
    )
    count_booked_rooms = await session.scalar(request)

    return count_booked_rooms


async def set_hotel(data: CreateHotelSchema, session: AsyncSession):
    new_hotel = Hotel(
        name=data.name,
        city=data.city,
        country=data.country,
        star_rating=data.star_rating,
        description=data.description,
        address=data.address
    )
    session.add(new_hotel)
    await session.flush()

    return new_hotel


async def update_hotel(data: UpdateHotelSchema, upd_hotel: Hotel, session: AsyncSession):
    upd_data = data.model_dump(exclude_unset=True)
    for key, value in upd_data.items():
        setattr(upd_hotel, key, value)

    return upd_hotel


async def hide_hotel(hotel: Hotel, session: AsyncSession):
    hotel.is_active = False


async def set_room_type(
    data: CreateRoomTypeSchema,
    hotel_id: int,
    session: AsyncSession
    ):
    new_room_type = RoomType(
        hotel_id=hotel_id,
        name=data.name,
        capacity=data.capacity,
        bed_type=data.bed_type,
        price_per_night=data.price_per_night,
        total_rooms=data.total_rooms
    )
    session.add(new_room_type)
    await session.flush()

    return new_room_type


async def update_room_type(data: UpdateRoomTypeSchema, upd_room_type: RoomType, session: AsyncSession):
    upd_data = data.model_dump(exclude_unset=True)
    for key, value in upd_data.items():
        setattr(upd_room_type, key, value)

    return upd_room_type
