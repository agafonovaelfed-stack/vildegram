import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Chat(Base, TimestampMixin):
    """Универсальный чат: direct | group | channel."""

    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(16), default="direct", index=True, nullable=False)

    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    # Системный чат (официальный VildeGram): нельзя писать, удалять, выходить
    is_service: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")

    members: Mapped[list["ChatMember"]] = relationship(
        "ChatMember",
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChatMember(Base):
    __tablename__ = "chat_members"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_chat_member"),)

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # owner | admin | member
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)

    # папки, mute, архив (per-user)
    is_pinned: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_muted: Mapped[bool] = mapped_column(default=False, nullable=False)

    chat: Mapped["Chat"] = relationship("Chat", back_populates="members")