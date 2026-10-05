import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str  # image | video | audio | voice | document | gif | sticker
    url: str
    thumbnail_url: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    waveform: str | None = None


class ReactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    emoji: str
    user_id: uuid.UUID


class MessageCreate(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    reply_to_id: uuid.UUID | None = None
    attachment_ids: list[uuid.UUID] = []
    ttl_seconds: int | None = Field(default=None, ge=0, le=86400)


class MessageUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID
    text: str | None = None
    kind: str = "regular"
    reply_to_id: uuid.UUID | None = None
    forwarded_from_chat_id: uuid.UUID | None = None
    forwarded_from_user_id: uuid.UUID | None = None
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    expires_at: datetime | None = None
    author_signature: str | None = None
    created_at: datetime
    attachments: list[AttachmentOut] = []
    reactions: list[ReactionOut] = []


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_before_id: uuid.UUID | None = None
    has_more: bool = False


class ReactionCreate(BaseModel):
    emoji: str = Field(min_length=1, max_length=64)


class ReadReceiptIn(BaseModel):
    chat_id: uuid.UUID
    last_read_message_id: uuid.UUID