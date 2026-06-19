from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.schemas.enums import PaymentStatus


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CheckoutResponseSchema(Base):
    confirmation_url: str


class PaymentInfoSchema(Base):
    id: int
    booking_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    paid_at: datetime | None = None
