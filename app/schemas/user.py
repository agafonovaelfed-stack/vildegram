import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str  # verified | scam | fake | v
    created_at: datetime


class UserPublic(BaseModel):
    """Публичный профиль — то, что видит любой другой юзер."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    is_online: bool = False
    last_seen: datetime | None = None
    badges: list[BadgeOut] = []


class UserMe(BaseModel):
    """Свой профиль — с email, телефоном и приватностью."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr
    phone: str | None = None
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    is_online: bool
    is_bot: bool
    created_at: datetime
    badges: list[BadgeOut] = []


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    bio: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=512)
    phone: str | None = Field(default=None, max_length=32)


class UserSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None
    is_online: bool = False
    badges: list[BadgeOut] = []

class PrivacySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    show_last_seen: str
    show_online: str
    show_avatar: str
    show_phone: str
    allow_messages: str
    allow_calls: str
    allow_groups: str
    allow_read_receipts: bool
    allow_typing_indicator: bool


class PrivacySettingsUpdate(BaseModel):
    show_last_seen: str | None = None
    show_online: str | None = None
    show_avatar: str | None = None
    show_phone: str | None = None
    allow_messages: str | None = None
    allow_calls: str | None = None
    allow_groups: str | None = None
    allow_read_receipts: bool | None = None
    allow_typing_indicator: bool | None = None
