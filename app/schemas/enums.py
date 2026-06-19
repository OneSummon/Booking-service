from enum import StrEnum


class UserStatus(StrEnum):
    user = "user"
    admin = "admin"


class BookingStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class PaymentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    cancelled = "cancelled"
    refunded = "refunded"


class BedTypeEnum(StrEnum):
    single = "single"
    double = "double"
    twin = "twin"
    queen = "queen"
    king = "king"