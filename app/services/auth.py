from datetime import timedelta
from app.config import settings
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.security import hash_obj, hash_token
from app.database.models import User, RefreshToken
from app.schemas.enums import UserStatus
from app.utils import utcnow


async def get_user(email: str, session: AsyncSession):
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_id(id: int, session: AsyncSession):
    return await session.scalar(select(User).where(User.id == id))


async def set_user(email: str, password: str, session: AsyncSession):
    new_user = User(
        email=email,
        password_hash=hash_obj(password),
        role=UserStatus.user
    )
    session.add(new_user)
    await session.flush()

    return new_user


async def set_refresh_token(refresh_token: str, user_id: int, session: AsyncSession):
    active_tokens = await session.scalars(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utcnow()
        )
        .order_by(RefreshToken.expires_at.asc())
        .with_for_update()
    )
    active_tokens = list(active_tokens)
    if len(active_tokens) >= settings.max_active_sessions:
        active_tokens[0].revoked_at = utcnow()

    new_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        expires_at=utcnow() + timedelta(days=settings.expire_refresh_token_days)
    )
    session.add(new_token)

    return new_token


async def get_hash_token(hash_token: str, session: AsyncSession):
    return await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token))


async def delete_inactive_tokens(user_id: int, session: AsyncSession):
    await session.execute(delete(RefreshToken).where(
        RefreshToken.user_id == user_id,
        or_(
              RefreshToken.expires_at < utcnow(),
              RefreshToken.revoked_at.is_not(None)
          )
    ))


async def revoke_all_tokens(user_id: int, session: AsyncSession):
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utcnow()
        )
        .values(revoked_at=utcnow())
    )
