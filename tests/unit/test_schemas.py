from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.auth import CreateUserSchema
from app.schemas.enums import BedTypeEnum
from app.schemas.hotels import (
    CreateRoomTypeSchema,
    HotelFiltersSchema,
    ReqDateSchema,
    UpdateRoomTypeSchema,
)
from app.schemas.user import ChangePasswordSchema


class TestCreateUserSchema:
    def test_valid(self):
        s = CreateUserSchema(email="User@Example.COM", password="password123")
        assert s.email == "user@example.com"

    def test_email_stripped_and_lowercased(self):
        s = CreateUserSchema(email="  TEST@EXAMPLE.COM  ", password="password123")
        assert s.email == "test@example.com"

    def test_invalid_email_format(self):
        with pytest.raises(ValidationError):
            CreateUserSchema(email="not-an-email", password="password123")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            CreateUserSchema(email="a@b.com", password="short")

    def test_password_too_long(self):
        with pytest.raises(ValidationError):
            CreateUserSchema(email="a@b.com", password="x" * 129)

    def test_password_at_min_length(self):
        s = CreateUserSchema(email="a@b.com", password="12345678")
        assert s.password == "12345678"

    def test_password_at_max_length(self):
        s = CreateUserSchema(email="a@b.com", password="x" * 128)
        assert len(s.password) == 128


class TestBedTypeEnum:
    @pytest.mark.parametrize("value", ["single", "double", "twin", "queen", "king"])
    def test_all_valid_values(self, value):
        assert BedTypeEnum(value) is not None

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            BedTypeEnum("futon")

    def test_invalid_value_case_sensitive(self):
        with pytest.raises(ValueError):
            BedTypeEnum("Double")


class TestCreateRoomTypeSchema:
    def test_valid(self):
        s = CreateRoomTypeSchema(
            name="Suite",
            capacity=2,
            bed_type="double",
            price_per_night=Decimal("150.00"),
            total_rooms=5,
        )
        assert s.bed_type == BedTypeEnum.double

    def test_invalid_bed_type(self):
        with pytest.raises(ValidationError):
            CreateRoomTypeSchema(
                name="Suite", capacity=2, bed_type="hammock",
                price_per_night=Decimal("150.00"), total_rooms=5,
            )

    def test_price_zero_rejected(self):
        with pytest.raises(ValidationError):
            CreateRoomTypeSchema(
                name="Suite", capacity=2, bed_type="double",
                price_per_night=Decimal("0.00"), total_rooms=5,
            )

    def test_capacity_zero_rejected(self):
        with pytest.raises(ValidationError):
            CreateRoomTypeSchema(
                name="Suite", capacity=0, bed_type="double",
                price_per_night=Decimal("100.00"), total_rooms=5,
            )

    def test_total_rooms_zero_rejected(self):
        with pytest.raises(ValidationError):
            CreateRoomTypeSchema(
                name="Suite", capacity=2, bed_type="double",
                price_per_night=Decimal("100.00"), total_rooms=0,
            )


class TestUpdateRoomTypeSchema:
    def test_all_optional_fields(self):
        s = UpdateRoomTypeSchema()
        assert s.name is None
        assert s.bed_type is None

    def test_partial_update_valid(self):
        s = UpdateRoomTypeSchema(price_per_night=Decimal("200.00"))
        assert s.price_per_night == Decimal("200.00")


class TestReqDateSchema:
    def _future(self, days):
        return datetime.utcnow() + timedelta(days=days)

    def test_valid_future_dates(self):
        s = ReqDateSchema(req_check_in=self._future(1), req_check_out=self._future(3))
        assert s.req_check_in < s.req_check_out

    def test_check_in_in_past_rejected(self):
        with pytest.raises(ValidationError):
            ReqDateSchema(
                req_check_in=datetime.utcnow() - timedelta(days=1),
                req_check_out=self._future(2),
            )

    def test_check_in_equals_check_out_rejected(self):
        t = self._future(2)
        with pytest.raises(ValidationError):
            ReqDateSchema(req_check_in=t, req_check_out=t)

    def test_check_in_after_check_out_rejected(self):
        with pytest.raises(ValidationError):
            ReqDateSchema(
                req_check_in=self._future(3),
                req_check_out=self._future(1),
            )

    def test_tz_aware_dates_normalized(self):
        from datetime import timezone
        aware_in = datetime.now(timezone.utc) + timedelta(days=1)
        aware_out = datetime.now(timezone.utc) + timedelta(days=3)
        s = ReqDateSchema(req_check_in=aware_in, req_check_out=aware_out)
        assert s.req_check_in.tzinfo is None
        assert s.req_check_out.tzinfo is None


class TestChangePasswordSchema:
    def test_valid(self):
        s = ChangePasswordSchema(
            current_password="oldpass123",
            new_password="newpass123",
            retry_new_password="newpass123",
        )
        assert s.new_password == "newpass123"

    def test_new_password_too_short(self):
        with pytest.raises(ValidationError):
            ChangePasswordSchema(
                current_password="oldpass",
                new_password="short",
                retry_new_password="short",
            )

    def test_new_password_too_long(self):
        with pytest.raises(ValidationError):
            ChangePasswordSchema(
                current_password="oldpass",
                new_password="x" * 129,
                retry_new_password="x" * 129,
            )


class TestHotelFiltersSchema:
    def test_defaults(self):
        s = HotelFiltersSchema()
        assert s.offset == 0
        assert s.limit == 20

    def test_min_star_rating_below_1_rejected(self):
        with pytest.raises(ValidationError):
            HotelFiltersSchema(min_star_rating=0.5)

    def test_max_star_rating_above_5_rejected(self):
        with pytest.raises(ValidationError):
            HotelFiltersSchema(max_star_rating=5.5)

    def test_valid_star_rating_bounds(self):
        s = HotelFiltersSchema(min_star_rating=1.0, max_star_rating=5.0)
        assert s.min_star_rating == 1.0

    def test_limit_too_high_rejected(self):
        with pytest.raises(ValidationError):
            HotelFiltersSchema(limit=201)

    def test_offset_negative_rejected(self):
        with pytest.raises(ValidationError):
            HotelFiltersSchema(offset=-1)
