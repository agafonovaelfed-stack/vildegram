import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    kind: str = Field(pattern=r"^(direct|group|channel)$")
    peer_id: uuid.UUID | None = None      # для direct
    title: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    is_public: bool = False
    username: str | None = Field(default=None, max_length=32)


class ChatMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    role: str
    is_pinned: bool = False
    is_archived: bool = False
    is_muted: bool = False


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    is_public: bool = False
    username: str | None = None
    is_service: bool = False
    created_at: datetime
    members: list[ChatMemberOut] = []


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    avatar_url: str | None = Field(default=None, max_length=512)
    is_public: bool | None = None


class ChatMemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(owner|admin|member)$")
    is_pinned: bool | None = None
    is_archived: bool | None = None
    is_muted: bool | None = None


class ChatInviteIn(BaseModel):
    user_ids: list[uuid.UUID]