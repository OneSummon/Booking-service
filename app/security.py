import hashlib
from app.schemas.enums import UserStatus
from app.config import settings
from fastapi import HTTPException, Request, status
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

pwd_context = CryptContext(schemes=["bcrypt"])


def hash_obj(object: str):
    return pwd_context.hash(object)


def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def verify(current_object: str, hashed_object: str):
    return pwd_context.verify(current_object, hashed_object)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=settings.expire_access_token_min)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_user_is_admin(user_role: UserStatus):
    if user_role != UserStatus.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have administrator rights")


def get_real_ip(request: Request):
    ip = request.headers.get("X-Real-IP")
    if ip is not None:
        return ip
    if request.client is None:
        return "unknown"
    return request.client.host
