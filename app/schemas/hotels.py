from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import BedTypeEnum


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateHotelSchema(Base):
    name: str
    city: str
    country: str
    star_rating: float = Field(ge=1, le=5)
    description: str
    address: str


class InfoHotelSchema(CreateHotelSchema):
    id: int
    is_active: bool


class UpdateHotelSchema(Base):
    name: str | None = None
    city: str | None = None
    country: str | None = None
    star_rating: float | None = Field(default=None, ge=1, le=5)
    description: str | None = None
    address: str | None = None
    is_active: bool | None = None


class CreateRoomTypeSchema(Base):
    name: str
    capacity: int = Field(ge=1)
    bed_type: BedTypeEnum
    price_per_night: Decimal = Field(ge=Decimal("0.01"))
    total_rooms: int = Field(ge=1)


class RoomTypeSchema(CreateRoomTypeSchema):
    id: int
    hotel_id: int


class UpdateRoomTypeSchema(Base):
    name: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    bed_type: BedTypeEnum | None = None
    price_per_night: Decimal | None = Field(default=None, ge=Decimal("0.01"))
    total_rooms: int | None = Field(default=None, ge=1)


class HotelDetailSchema(InfoHotelSchema):
    room_types: list[RoomTypeSchema]


class HotelFiltersSchema(Base):
    name: str | None = None
    city: str | None = None
    country: str | None = None
    min_star_rating: float | None = Field(default=None, ge=1.0, le=5.0)
    max_star_rating: float | None = Field(default=None, ge=1.0, le=5.0)
    address: str | None = None

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=200)


class ReqDateSchema(Base):
    req_check_in: datetime
    req_check_out: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> "ReqDateSchema":
        req_check_in_utc = self.req_check_in.astimezone(timezone.utc).replace(tzinfo=None) if self.req_check_in.tzinfo else self.req_check_in
        if req_check_in_utc < datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError("check_in can't be in the past")

        req_check_out_utc = self.req_check_out.astimezone(timezone.utc).replace(tzinfo=None) if self.req_check_out.tzinfo else self.req_check_out
        if req_check_in_utc >= req_check_out_utc:
            raise ValueError("check_in must be before check_out")
        self.req_check_in = req_check_in_utc
        self.req_check_out = req_check_out_utc
        return self


class AvailabilityOutputSchema(Base):
    available: bool
    count_available_rooms: int | None = None
    requested_date: str
