import uvicorn
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

from app.config import settings
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis.asyncio import Redis

from app.logging_config import setup_logging
from app.yookassa_config import yookassa_init
from app.correlation import CorrelationIDMiddleware
setup_logging()

from app.routers.auth import router as auth_router
from app.routers.hotels import router as hotel_router
from app.routers.bookings import router as booking_router
from app.routers.admin import router as admin_router
from app.routers.user import router as user_router
from app.routers.payments import router as payment_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.cache_storage)
    FastAPICache.init(RedisBackend(redis), prefix="cache")
    yookassa_init() # инициализация Юкассы
    yield
    await redis.aclose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CorrelationIDMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(hotel_router, prefix="/api/v1")
app.include_router(booking_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")

@app.get("/health")
@limiter.limit("100/minute")
async def check(request: Request):
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)