import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    action: str
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    payload: dict | None = None
    note: str | None = None
    created_at: datetime


class ReportCreate(BaseModel):
    target_type: str = Field(pattern=r"^(user|message|chat|group|channel)$")
    target_id: uuid.UUID
    reason: str = Field(pattern=r"^(spam|scam|violence|adult|impersonation|other)$")
    comment: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reporter_id: uuid.UUID | None = None
    target_type: str
    target_id: uuid.UUID
    reason: str
    comment: str | None = None
    status: str
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    resolution_note: str | None = None
    created_at: datetime


class ReportResolve(BaseModel):
    status: str = Field(pattern=r"^(reviewed|resolved|dismissed)$")
    resolution_note: str | None = Field(default=None, max_length=2000)


class UserBanIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class StatsOut(BaseModel):
    total_users: int
    online_users: int
    total_chats: int
    total_messages: int
    total_calls: int
    pending_reports: int