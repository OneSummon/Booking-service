import uuid
from typing import Annotated
from app.database.models import User
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.config import settings
from app.session_dep import SessionDep
from app.services.auth import get_user_by_id, set_refresh_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(session: SessionDep, token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
        if role not in ["user", "admin"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission")
        user = await get_user_by_id(int(user_id), session)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not found")
        return user
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="jwt error")


async def create_refresh_token(user_id: int, session: SessionDep) -> str:
    token = str(uuid.uuid4())
    await set_refresh_token(token, user_id, session)
    return token


CurrentUserDep = Annotated[User, Depends(get_current_user)]
