from datetime import timedelta

import pytest
from sqlalchemy import select

from app.database.models import RefreshToken
from app.schemas.enums import UserStatus
from app.security import hash_token
from app.services.auth import (
    delete_inactive_tokens,
    get_hash_token,
    get_user,
    get_user_by_id,
    revoke_all_tokens,
    set_refresh_token,
    set_user,
)
from app.utils import utcnow


@pytest.fixture
async def user(session):
    return await set_user("user@test.com", "password123", session)


class TestSetUser:
    async def test_creates_user_with_correct_email(self, session):
        user = await set_user("alice@test.com", "password123", session)
        assert user.id is not None
        assert user.email == "alice@test.com"

    async def test_password_is_hashed(self, session):
        user = await set_user("bob@test.com", "password123", session)
        assert user.password_hash != "password123"

    async def test_default_role_is_user(self, session):
        user = await set_user("carol@test.com", "password123", session)
        assert user.role == UserStatus.user

    async def test_flush_assigns_id(self, session):
        user = await set_user("dave@test.com", "password123", session)
        assert isinstance(user.id, int)
        assert user.id > 0


class TestGetUser:
    async def test_finds_existing_user(self, session, user):
        found = await get_user("user@test.com", session)
        assert found is not None
        assert found.id == user.id

    async def test_returns_none_for_missing_email(self, session):
        assert await get_user("nobody@test.com", session) is None


class TestGetUserById:
    async def test_finds_existing_user(self, session, user):
        found = await get_user_by_id(user.id, session)
        assert found is not None
        assert found.email == user.email

    async def test_returns_none_for_unknown_id(self, session):
        assert await get_user_by_id(999999, session) is None


class TestSetRefreshToken:
    async def test_creates_token_with_correct_hash(self, session, user):
        token = await set_refresh_token("myrawtoken", user.id, session)
        assert token.user_id == user.id
        assert token.token_hash == hash_token("myrawtoken")

    async def test_new_token_is_not_revoked(self, session, user):
        token = await set_refresh_token("mytoken", user.id, session)
        assert token.revoked_at is None

    async def test_evicts_oldest_when_max_sessions_exceeded(self, session, user):
        from app.config import settings

        tokens = []
        for i in range(settings.max_active_sessions):
            t = await set_refresh_token(f"token{i}", user.id, session)
            tokens.append(t)

        await set_refresh_token("overflow_token", user.id, session)

        assert tokens[0].revoked_at is not None

    async def test_does_not_evict_when_under_limit(self, session, user):
        from app.config import settings

        tokens = []
        for i in range(settings.max_active_sessions - 1):
            t = await set_refresh_token(f"tok{i}", user.id, session)
            tokens.append(t)

        assert all(t.revoked_at is None for t in tokens)


class TestGetHashToken:
    async def test_finds_existing_token(self, session, user):
        await set_refresh_token("lookup_token", user.id, session)
        found = await get_hash_token(hash_token("lookup_token"), session)
        assert found is not None

    async def test_returns_none_for_unknown_hash(self, session):
        assert await get_hash_token("nonexistent_hash", session) is None


class TestDeleteInactiveTokens:
    async def test_removes_expired_token(self, session, user):
        expired = RefreshToken(
            user_id=user.id,
            token_hash="expired_hash",
            expires_at=utcnow() - timedelta(hours=1),
        )
        session.add(expired)
        await session.flush()

        await delete_inactive_tokens(user.id, session)
        await session.flush()

        result = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == "expired_hash")
        )
        assert result is None

    async def test_removes_revoked_token(self, session, user):
        revoked = RefreshToken(
            user_id=user.id,
            token_hash="revoked_hash",
            expires_at=utcnow() + timedelta(days=7),
            revoked_at=utcnow(),
        )
        session.add(revoked)
        await session.flush()

        await delete_inactive_tokens(user.id, session)
        await session.flush()

        result = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == "revoked_hash")
        )
        assert result is None

    async def test_keeps_active_token(self, session, user):
        active = await set_refresh_token("active_token", user.id, session)
        await delete_inactive_tokens(user.id, session)
        await session.flush()

        result = await session.scalar(
            select(RefreshToken).where(RefreshToken.id == active.id)
        )
        assert result is not None


class TestRevokeAllTokens:
    async def test_revokes_all_active_tokens(self, session, user):
        for i in range(2):
            await set_refresh_token(f"active_{i}", user.id, session)

        await revoke_all_tokens(user.id, session)
        await session.flush()

        remaining = await session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        assert len(remaining.all()) == 0

    async def test_does_not_touch_already_expired_tokens(self, session, user):
        expired = RefreshToken(
            user_id=user.id,
            token_hash="already_expired",
            expires_at=utcnow() - timedelta(days=1),
        )
        session.add(expired)
        await session.flush()

        await revoke_all_tokens(user.id, session)
        await session.flush()

        # expired tokens are not touched by revoke_all (they were already past expiry)
        result = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == "already_expired")
        )
        assert result.revoked_at is None
