from datetime import datetime, timedelta

from app.utils import utcnow


def test_returns_naive_datetime():
    result = utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is None


def test_is_close_to_utc_now():
    before = datetime.utcnow()
    result = utcnow()
    after = datetime.utcnow()
    assert before <= result <= after


def test_two_calls_are_ordered():
    t1 = utcnow()
    t2 = utcnow()
    assert t1 <= t2


def test_advances_over_time():
    t1 = utcnow()
    t2 = utcnow() + timedelta(seconds=1)
    assert t2 > t1
