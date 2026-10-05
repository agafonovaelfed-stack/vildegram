from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

# Удобный алиас, чтобы в роутерах писать: db: DBSession
DBSession = Annotated[AsyncSession, Depends(get_session)]