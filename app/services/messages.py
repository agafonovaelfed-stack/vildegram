import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.message import Message
from app.models.block import Block
from app.models.chat import Chat, ChatMember
from app.repositories.chats import ChatRepository
from app.repositories.messages import MessageRepository


class MessageError(Exception):
    pass


class MessageNotFound(MessageError):
    pass


class NotAMember(MessageError):
    pass


class EmptyMessage(MessageError):
    pass


class NotAuthor(MessageError):
    pass


class MessageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.messages = MessageRepository(db)
        self.chats = ChatRepository(db)

    async def _assert_member(
        self, chat_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        if not await self.chats.is_member(chat_id, user_id):
            raise NotAMember("You are not a member of this chat")

    async def get(self, message_id: uuid.UUID) -> Message:
        msg = await self.messages.get_by_id(message_id)
        if msg is None or msg.deleted_at is not None:
            raise MessageNotFound("Message not found")
        return msg

    async def send(
        self,
        *,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        text: str | None = None,
        reply_to_id: uuid.UUID | None = None,
        attachment_ids: list[uuid.UUID] | None = None,
        ttl_seconds: int | None = None,
    ) -> Message:
        await self._assert_member(chat_id, sender_id)

        chat = await self.chats.get_by_id(chat_id)
        if chat is not None and chat.kind == "direct":
            peer_ids = (await self.db.execute(select(ChatMember.user_id).where(ChatMember.chat_id == chat_id, ChatMember.user_id != sender_id))).scalars().all()
            if peer_ids:
                blocked = (await self.db.execute(select(Block.id).where(Block.blocker_id == sender_id, Block.blocked_id.in_(peer_ids)))).scalar_one_or_none()
                blocked_by = (await self.db.execute(select(Block.id).where(Block.blocker_id.in_(peer_ids), Block.blocked_id == sender_id))).scalar_one_or_none()
                if blocked or blocked_by:
                    raise NotAMember("Сообщения этому пользователю недоступны")

        from app.repositories.chats import ChatRepository as _CR
        _chat = await _CR(self.db).get_by_id(chat_id)
        if _chat is not None and getattr(_chat, "is_service", False):
            raise NotAMember("Системный чат доступен только для чтения")

        has_text = bool(text and text.strip())
        has_attach = bool(attachment_ids)
        if not has_text and not has_attach:
            raise EmptyMessage("Message must contain text or attachment")

        msg = await self.messages.create(
            chat_id=chat_id,
            sender_id=sender_id,
            text=text.strip() if has_text else None,
            reply_to_id=reply_to_id,
            ttl_seconds=ttl_seconds,
        )

        # Привязка вложений: получаем их через репозиторий и переназначаем message_id
        for att_id in (attachment_ids or []):
            att = await self.messages.get_attachment(att_id)
            if att is not None:
                att.message_id = msg.id

        await self.messages.increment_unread(chat_id, exclude_user_id=sender_id)
        await self.db.commit()
        # Перечитываем с relations, чтобы вернуть полное сообщение
        full = await self.messages.get_by_id(msg.id)
        return full if full is not None else msg

    async def history(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
    ) -> list[Message]:
        await self._assert_member(chat_id, user_id)
        return await self.messages.list_history(
            chat_id, limit=limit, before_id=before_id
        )

    async def edit(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
    ) -> Message:
        msg = await self.get(message_id)
        if msg.sender_id != user_id:
            raise NotAuthor("You can only edit your own messages")
        if not text.strip():
            raise EmptyMessage("Message cannot be empty")
        updated = await self.messages.update_text(msg, text.strip())
        await self.db.commit()
        return updated

    async def delete(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        msg = await self.get(message_id)
        # Автор или админ чата может удалить (проверку роли оставим на потом)
        if msg.sender_id != user_id:
            raise NotAuthor("You can only delete your own messages")
        await self.messages.soft_delete(msg)
        await self.db.commit()

    async def add_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> dict:
        msg = await self.get(message_id)
        await self._assert_member(msg.chat_id, user_id)
        await self.messages.add_reaction(
            message_id=message_id, user_id=user_id, emoji=emoji
        )
        await self.db.commit()
        return {"chat_id": str(msg.chat_id), "message_id": str(message_id), "user_id": str(user_id), "emoji": 
emoji}

    async def remove_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> dict:
        msg = await self.get(message_id)
        await self._assert_member(msg.chat_id, user_id)
        await self.messages.remove_reaction(
            message_id=message_id, user_id=user_id, emoji=emoji
        )
        await self.db.commit()
        return {"chat_id": str(msg.chat_id), "message_id": str(message_id), "user_id": str(user_id), "emoji": 
emoji}

    async def mark_read(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        last_message_id: uuid.UUID,
    ) -> None:
        await self._assert_member(chat_id, user_id)
        await self.messages.mark_read(
            chat_id=chat_id,
            user_id=user_id,
            last_message_id=last_message_id,
        )
        await self.db.commit()