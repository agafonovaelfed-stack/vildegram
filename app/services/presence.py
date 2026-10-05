import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.users import UserRepository


class PresenceService:
    """Онлайн/оффлайн статус. Для одного инстанса — in-memory, для прод — Redis pub/sub.

    Здесь держим простую in-memory реализацию. Позже легко заменить на Redis.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def set_online(self, user_id: uuid.UUID) -> None:
        await self.users.set_online(user_id, True)
        await self.db.commit()

    async def set_offline(self, user_id: uuid.UUID) -> None:
        await self.users.set_online(user_id, False)
        await self.db.commit()