from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.database.database import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
