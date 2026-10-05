import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BadgeCreate(BaseModel):
    user_id: uuid.UUID
    kind: str = Field(pattern=r"^(verified|scam|fake|v)$")
    reason: str | None = Field(default=None, max_length=255)


class BadgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    kind: str
    reason: str | None = None
    revocable: bool
    created_at: datetime


class BadgeRevoke(BaseModel):
    badge_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=255)