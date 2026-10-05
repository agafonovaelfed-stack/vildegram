import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat, ChatMember


class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, chat_id: uuid.UUID) -> Chat | None:
        return await self.db.get(Chat, chat_id)

    async def get_by_username(self, username: str) -> Chat | None:
        stmt = select(Chat).where(func.lower(Chat.username) == username.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_member(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> ChatMember | None:
        stmt = select(ChatMember).where(
            and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        include_archived: bool = False,
    ) -> list[tuple[Chat, ChatMember]]:
        stmt = (
            select(Chat, ChatMember)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .where(ChatMember.user_id == user_id)
        )
        if not include_archived:
            stmt = stmt.where(ChatMember.is_archived.is_(False))
        stmt = stmt.order_by(
            ChatMember.is_pinned.desc(),
            Chat.updated_at.desc(),
        )
        return list((await self.db.execute(stmt)).all())

    async def find_direct_between(
        self, user_a: uuid.UUID, user_b: uuid.UUID
    ) -> Chat | None:
        sub = (
            select(ChatMember.chat_id)
            .where(ChatMember.user_id.in_([user_a, user_b]))
            .group_by(ChatMember.chat_id)
            .having(func.count(ChatMember.user_id) == 2)
        )
        candidate_ids = [row[0] for row in (await self.db.execute(sub)).all()]
        if not candidate_ids:
            return None
        stmt = (
            select(Chat)
            .where(Chat.id.in_(candidate_ids))
            .where(Chat.kind == "direct")
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        kind: str,
        created_by: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        is_public: bool = False,
        username: str | None = None,
        is_service: bool = False,
    ) -> Chat:
        chat = Chat(
            kind=kind,
            created_by=created_by,
            title=title,
            description=description,
            is_public=is_public,
            username=username,
            is_service=is_service,
        )
        self.db.add(chat)
        await self.db.flush()
        return chat

    async def add_member(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        role: str = "member",
    ) -> ChatMember:
        member = ChatMember(chat_id=chat_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.flush()
        return member

    async def remove_member(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.get_member(chat_id, user_id)
        if member is not None:
            await self.db.delete(member)
            await self.db.flush()

    async def update_chat(self, chat: Chat, **fields) -> Chat:
        for key, value in fields.items():
            if hasattr(chat, key) and value is not None:
                setattr(chat, key, value)
        await self.db.flush()
        return chat

    async def update_member(self, member: ChatMember, **fields) -> ChatMember:
        for key, value in fields.items():
            if hasattr(member, key) and value is not None:
                setattr(member, key, value)
        await self.db.flush()
        return member

    async def member_ids(self, chat_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def is_member(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(ChatMember.user_id).where(
            and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def search_public(
        self, query: str, *, limit: int = 20
    ) -> list[Chat]:
        pattern = f"%{query.lower()}%"
        stmt = (
            select(Chat)
            .where(Chat.is_public.is_(True))
            .where(
                or_(
                    func.lower(Chat.username).like(pattern),
                    func.lower(Chat.title).like(pattern),
                )
            )
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())