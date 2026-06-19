import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(url=settings.db_url, echo=False)

async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with async_session() as session:
        logger.debug("Сессия БД открыта")

        try:
            yield session
            await session.commit()

            logger.debug("Сессия с БД успешно закрыта")
        except Exception as e:
            await session.rollback()
            
            logger.error(f"Сессия с Бд закрыта с ошибкой: {e}", exc_info=True)
            raise