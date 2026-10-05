import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CallStartIn(BaseModel):
    peer_id: uuid.UUID | None = None      # для 1-на-1
    chat_id: uuid.UUID | None = None      # для звонка в чате/группе
    kind: str = Field(default="audio", pattern=r"^(audio|video|group_audio|group_video)$")


class CallParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    state: str
    joined_at: datetime | None = None
    left_at: datetime | None = None
    is_muted: bool
    is_video_on: bool
    is_screen_sharing: bool


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID | None = None
    initiator_id: uuid.UUID | None = None
    kind: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    end_reason: str | None = None
    is_recorded: bool = False
    recording_url: str | None = None
    created_at: datetime
    participants: list[CallParticipantOut] = []


class CallActionIn(BaseModel):
    call_id: uuid.UUID


class CallUpdateIn(BaseModel):
    is_muted: bool | None = None
    is_video_on: bool | None = None
    is_screen_sharing: bool | None = None


class IceServerOut(BaseModel):
    urls: list[str]
    username: str | None = None
    credential: str | None = None