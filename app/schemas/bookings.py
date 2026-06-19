from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import BookingStatus

class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class CreateBookingSchema(Base):
    room_type_id: int
    check_in: datetime
    check_out: datetime
    guests_count: int = Field(ge=1)

class InfoBookingSchema(CreateBookingSchema):
    id: int
    user_id: int
    status: BookingStatus
    total_price: Decimal
    created_at: datetime
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

class CancelBookingSchema(Base):
    cancellation_reason: str | None = None

class BookingFilterSchema(Base):
    room_type_id: int | None = None
    check_in: datetime | None = None
    check_out: datetime | None = None
    guests_count: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    status: BookingStatus | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=200)

    @model_validator(mode="after")
    def normalize_datetimes(self) -> "BookingFilterSchema":
        for field in ("check_in", "check_out", "created_from", "created_to"):
            value = getattr(self, field)
            if value is not None and value.tzinfo is not None:
                setattr(self, field, value.astimezone(timezone.utc).replace(tzinfo=None))
        return self
