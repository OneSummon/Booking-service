from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Booking, Payment, RefreshToken, User
from app.schemas.auth import RefreshTokenSchema
from app.schemas.user import UpdateUserSchema
from app.security import hash_obj, hash_token
from app.utils import utcnow


async def get_user(user_id: int, session: AsyncSession):
    return await session.scalar(select(User).where(User.id == user_id))


async def update_profile(user_id: int, data: UpdateUserSchema, session: AsyncSession):
    user = await get_user(user_id, session)
    upd_data = data.model_dump(exclude_unset=True)

    for key, value in upd_data.items():
        setattr(user, key, value)

    user.updated_at = utcnow()
    await session.flush()

    return user


async def delete_account(user_id: int, session: AsyncSession):
    user = await get_user(user_id, session)

    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    booking_ids = list(await session.scalars(select(Booking.id).where(Booking.user_id == user_id)))
    if booking_ids:
        await session.execute(delete(Payment).where(Payment.booking_id.in_(booking_ids)))
        await session.execute(delete(Booking).where(Booking.id.in_(booking_ids)))

    await session.delete(user)


async def token_revoke(refresh_token: RefreshTokenSchema, session: AsyncSession, user_id: int) -> bool:
    token_hash = hash_token(refresh_token.refresh_token)
    token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id
        )
    )
    if token is None:
        return False
    token.revoked_at = utcnow()
    return True


async def change_password(new_password: str, user_id: int, session: AsyncSession):
    user = await get_user(user_id, session)

    user.password_hash = hash_obj(new_password)
    user.updated_at = utcnow()
