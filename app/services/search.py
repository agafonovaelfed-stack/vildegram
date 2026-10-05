import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.user import User
from app.repositories.chats import ChatRepository
from app.repositories.users import UserRepository


class SearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users_repo = UserRepository(db)
        self.chats_repo = ChatRepository(db)

    async def users(self, query: str, *, exclude_id: uuid.UUID) -> list[User]:
        return await self.users_repo.search(query, exclude_id=exclude_id)

    async def chats(self, query: str) -> list[Chat]:
        return await self.chats_repo.search_public(query)

    async def global_search(
        self, query: str, *, exclude_id: uuid.UUID, limit: int = 20
    ) -> dict:
        users = await self.users_repo.search(
            query, exclude_id=exclude_id, limit=limit
        )
        chats = await self.chats_repo.search_public(query, limit=limit)
        return {"users": users, "chats": chats}
