from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, Index, Numeric, String, ForeignKey, Text, Enum, UniqueConstraint
from decimal import Decimal
from datetime import datetime
from app.schemas.enums import UserStatus, BookingStatus, PaymentStatus
from app.utils import utcnow


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(50))
    last_name: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    role: Mapped[UserStatus] = mapped_column(Enum(UserStatus, create_type=True))

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(50), index=True)
    country: Mapped[str] = mapped_column(String(50), index=True)
    star_rating: Mapped[float] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        CheckConstraint("star_rating BETWEEN 1 AND 5", name="ck_star_rating_between_1_and_5"),
        UniqueConstraint("name", "country", "city", "address", name="uq_hotel_name_location"),
    )

    room_types: Mapped[list["RoomType"]] = relationship(
        back_populates="hotel",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(index=True)
    bed_type: Mapped[str] = mapped_column(String(20), index=True)
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_rooms: Mapped[int]

    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_capacity_positive"),
        CheckConstraint("price_per_night > 0", name="ck_price_per_night_positive"),
        CheckConstraint("total_rooms > 0", name="ck_total_rooms_positive"),
    )

    hotel: Mapped["Hotel"] = relationship(
        back_populates="room_types"
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="room_type"
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True)
    check_in: Mapped[datetime]
    check_out: Mapped[datetime]
    guests_count: Mapped[int]
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus, create_type=True), default=BookingStatus.pending)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    cancelled_at: Mapped[datetime | None]
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_booking_check_in_check_out", "check_in", "check_out"),
        CheckConstraint("check_out > check_in", name="ck_date_positive"),
        CheckConstraint("total_price > 0", name="ck_total_price_positive"),
        CheckConstraint("guests_count > 0", name="ck_guests_count_positive"),
    )

    room_type: Mapped["RoomType"] = relationship(
        back_populates="bookings"
    )

    user: Mapped["User"] = relationship(
        back_populates="bookings"
    )

    payment: Mapped["Payment | None"] = relationship(
        back_populates="booking",
        lazy="selectin"
    )

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, create_type=True), default=PaymentStatus.pending)
    provider_tx_id: Mapped[str | None] = mapped_column(unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(index=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_amount_positive"),
    )

    booking: Mapped["Booking"] = relationship(
        back_populates="payment",
        lazy="selectin"
    )

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)