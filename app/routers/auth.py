import logging
from app.limiter import limiter
from fastapi import APIRouter, HTTPException, Depends, Request, status
from sqlalchemy.exc import IntegrityError
from fastapi.security import OAuth2PasswordRequestForm
from app.dependencies import CurrentUserDep, create_refresh_token
from app.session_dep import SessionDep
from app.schemas.auth import CreateUserSchema, RefreshTokenSchema, TokenSchema
from app.schemas.user import InfoUserSchema
from app.security import create_access_token, hash_token, verify
from app.services.auth import get_hash_token, get_user, set_user, delete_inactive_tokens, get_user_by_id
from app.utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=InfoUserSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, user_data: CreateUserSchema, session: SessionDep):
    logger.debug("Начало регистрации")
    exist_user = await get_user(user_data.email, session)

    if exist_user is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    try:
        new_user = await set_user(
            user_data.email,
            user_data.password,
            session
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    logger.debug(f"Зарегистрирован пользователь, id: {new_user.id}")
    return new_user


@router.post("/login", response_model=TokenSchema, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def login(request: Request, session: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    logger.debug("Начало логина")
    user = await get_user(form_data.username, session)

    if not user or not verify(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.debug("Создание access_token")
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value
        }
    )

    logger.debug("Создание refresh_token")
    refresh_token = await create_refresh_token(user.id, session)

    logger.debug(f"Удаление просроченных токенов пользователя, id: {user.id}")
    await delete_inactive_tokens(user.id, session)

    logger.debug(f"Успешный логин, id: {user.id}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/refresh", response_model=TokenSchema, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def refresh(request: Request, refresh_token: RefreshTokenSchema, session: SessionDep):
    logger.debug("Начало обновления токена")
    token_hash = hash_token(refresh_token.refresh_token)

    exist_hash_token = await get_hash_token(token_hash, session)
    if not exist_hash_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token not found or invalid")

    if exist_hash_token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has already been revoked")

    if exist_hash_token.expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")

    user_id = exist_hash_token.user_id
    current_user = await get_user_by_id(user_id, session)

    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    exist_hash_token.revoked_at = utcnow()
    await session.flush()
    session.expunge(exist_hash_token)
    logger.debug(f"Токен отозван, user_id: {user_id}")

    new_refresh_token = await create_refresh_token(user_id, session)
    new_access_token = create_access_token(
        {
            "sub": str(user_id),
            "role": current_user.role.value
        }
    )

    logger.debug(f"Удаление просроченных токенов пользователя, id: {user_id}")
    await delete_inactive_tokens(user_id, session)

    logger.debug(f"Созданы новые токены, user_id: {user_id}")
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
    }


@router.post("/logout", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def logout(request: Request, refresh_token: RefreshTokenSchema, current_user: CurrentUserDep, session: SessionDep):
    logger.debug("Начало логаута")
    token_hash = hash_token(refresh_token.refresh_token)

    exist_hash_token = await get_hash_token(token_hash, session)
    if not exist_hash_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token hash not found")

    if exist_hash_token.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not belong to current user")

    exist_hash_token.revoked_at = utcnow()

    logger.debug(f"Пользователь успешно вышел из аккаунта, user_id: {current_user.id}")
    return {"logout": "success"}
