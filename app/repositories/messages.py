import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.models.message import Message
from app.models.reaction import Reaction
from app.models.read import ReadState


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.id == message_id)
            .options(
                selectinload(Message.reactions),
                selectinload(Message.attachments),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        text: str | None = None,
        kind: str = "regular",
        reply_to_id: uuid.UUID | None = None,
        ttl_seconds: int | None = None,
    ) -> Message:
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc).replace(microsecond=0)
            expires_at = expires_at.timestamp() + ttl_seconds
            expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)

        msg = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            text=text,
            kind=kind,
            reply_to_id=reply_to_id,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def list_history(
        self,
        chat_id: uuid.UUID,
        *,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .where(Message.deleted_at.is_(None))
            .options(
                selectinload(Message.reactions),
                selectinload(Message.attachments),
            )
        )
        if before_id is not None:
            ref = await self.db.get(Message, before_id)
            if ref is not None:
                stmt = stmt.where(Message.created_at < ref.created_at)
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        rows.reverse()
        return rows

    async def update_text(self, msg: Message, text: str) -> Message:
        msg.text = text
        msg.edited_at = datetime.now(timezone.utc)
        await self.db.flush()
        return msg

    async def soft_delete(self, msg: Message) -> None:
        msg.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def attach_file(
        self,
        message_id: uuid.UUID,
        *,
        kind: str,
        storage_key: str,
        url: str,
        thumbnail_url: str | None = None,
        original_filename: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        width: int | None = None,
        height: int | None = None,
        duration_seconds: int | None = None,
        waveform: str | None = None,
    ) -> Attachment:
        att = Attachment(
            message_id=message_id,
            kind=kind,
            storage_key=storage_key,
            url=url,
            thumbnail_url=thumbnail_url,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            waveform=waveform,
        )
        self.db.add(att)
        await self.db.flush()
        return att

    async def get_attachment(self, attachment_id: uuid.UUID) -> Attachment | None:
        return await self.db.get(Attachment, attachment_id)

    async def add_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> Reaction:
        existing = await self.get_reaction(message_id, user_id, emoji)
        if existing is not None:
            return existing
        r = Reaction(message_id=message_id, user_id=user_id, emoji=emoji)
        self.db.add(r)
        await self.db.flush()
        return r

    async def get_reaction(
        self,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> Reaction | None:
        stmt = select(Reaction).where(
            and_(
                Reaction.message_id == message_id,
                Reaction.user_id == user_id,
                Reaction.emoji == emoji,
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def remove_reaction(
        self,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        emoji: str,
    ) -> None:
        r = await self.get_reaction(message_id, user_id, emoji)
        if r is not None:
            await self.db.delete(r)
            await self.db.flush()

    async def mark_read(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        last_message_id: uuid.UUID,
    ) -> ReadState:
        state = await self.db.get(ReadState, {"chat_id": chat_id, "user_id": user_id})
        if state is None:
            state = ReadState(
                chat_id=chat_id,
                user_id=user_id,
                last_read_message_id=last_message_id,
                unread_count=0,
            )
            self.db.add(state)
        else:
            state.last_read_message_id = last_message_id
            state.last_read_at = datetime.now(timezone.utc)
            state.unread_count = 0
        await self.db.flush()
        return state

    async def increment_unread(self, chat_id: uuid.UUID, exclude_user_id: uuid.UUID) -> None:
        stmt = (
            update(ReadState)
            .where(ReadState.chat_id == chat_id)
            .where(ReadState.user_id != exclude_user_id)
            .values(unread_count=ReadState.unread_count + 1)
        )
        await self.db.execute(stmt)