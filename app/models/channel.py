import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Channel(Base, TimestampMixin):
    """Канал: подписчики, посты, комментарии."""

    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    # Настройки канала
    allow_comments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_reactions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sign_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subscriber_count: Mapped[int] = mapped_column(default=0, nullable=False)

    subscribers: Mapped[list["ChannelSubscriber"]] = relationship(
        "ChannelSubscriber",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChannelSubscriber(Base):
    __tablename__ = "channel_subscribers"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_subscriber"),
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # owner | admin | subscriber
    role: Mapped[str] = mapped_column(String(16), default="subscriber", nullable=False)

    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    channel: Mapped["Channel"] = relationship("Channel", back_populates="subscribers")