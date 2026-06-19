import logging

from app.limiter import limiter
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from app.schemas.auth import RefreshTokenSchema
from app.schemas.user import ChangePasswordSchema, InfoUserSchema, UpdateUserSchema
from app.services.auth import revoke_all_tokens
from app.services.user import change_password, get_user, token_revoke, update_profile, delete_account
from app.security import verify
from app.session_dep import SessionDep
from app.dependencies import CurrentUserDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=InfoUserSchema, status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def get_my_profile(request: Request, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Запрос профиля, user_id: {current_user.id}")
    user_profile = await get_user(current_user.id, session)
    return user_profile


@router.patch("/me", response_model=InfoUserSchema, status_code=status.HTTP_200_OK)
@limiter.limit("50/minute")
async def update_my_profile(request: Request, data: UpdateUserSchema, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Начало обновления профиля, user_id: {current_user.id}")
    try:
        user_profile = await update_profile(current_user.id, data, session)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
    logger.debug(f"Профиль обновлён, user_id: {current_user.id}")
    return user_profile


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_my_account(request: Request, refresh_token: RefreshTokenSchema, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Начало удаления аккаунта, user_id: {current_user.id}")
    revoked = await token_revoke(refresh_token, session, current_user.id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found")
    await delete_account(current_user.id, session)
    logger.debug(f"Аккаунт удалён, user_id: {current_user.id}")


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_my_password(request: Request, data: ChangePasswordSchema, current_user: CurrentUserDep, session: SessionDep):
    logger.debug(f"Начало смены пароля, user_id: {current_user.id}")
    if not verify(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    if data.retry_new_password != data.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The new passwords do not match")

    await change_password(data.new_password, current_user.id, session)
    await revoke_all_tokens(current_user.id, session)
    logger.debug(f"Пароль изменён, user_id: {current_user.id}")
