import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Call(Base, TimestampMixin):
    """Звонок.

    kind: audio | video | group_audio | group_video
    status: ringing | active | ended | missed | declined | failed
    """

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"), index=True, nullable=True
    )
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    kind: Mapped[str] = mapped_column(String(16), default="audio", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ringing", index=True, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Причина завершения: hangup | timeout | rejected | error
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Запись звонка
    is_recorded: Mapped[bool] = mapped_column(default=False, nullable=False)
    recording_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    participants: Mapped[list["CallParticipant"]] = relationship(
        "CallParticipant",
        back_populates="call",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CallParticipant(Base):
    __tablename__ = "call_participants"

    call_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # invited | ringing | joined | left | declined | missed
    state: Mapped[str] = mapped_column(String(16), default="invited", nullable=False)

    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_muted: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_video_on: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_screen_sharing: Mapped[bool] = mapped_column(default=False, nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="participants")