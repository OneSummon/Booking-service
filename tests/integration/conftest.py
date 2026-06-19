import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.fixture(autouse=True)
def mock_send_email(mocker):
    return mocker.patch("app.celery_app.send_email.delay")


@pytest.fixture
async def session(test_engine):
    """
    Truncates all tables before each test, then provides a fresh session.

    Rollback-based isolation fails here because SQLAlchemy does not issue
    ROLLBACK on connections it does not own, and asyncpg savepoints conflict
    with FOR UPDATE locks used in set_refresh_token. TRUNCATE gives the same
    clean-slate guarantee without any of those complications.
    """
    async with test_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE refresh_tokens, payments, bookings, room_types, hotels, users"
            " RESTART IDENTITY CASCADE"
        ))

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        await sess.close()
