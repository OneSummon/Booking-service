from slowapi import Limiter
from app.config import settings
from app.security import get_real_ip

limiter = Limiter(
    key_func=get_real_ip,
    storage_uri=settings.rate_limiting_storage
)
