import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Reaction(Base, TimestampMixin):
    """Реакция на сообщение.

    emoji: сам эмодзи ('👍', '❤️', '🔥', '😂', '😮', '😢', '🎉', '👎')
    или кастомный идентификатор стикера.
    """

    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_user_emoji"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    emoji: Mapped[str] = mapped_column(String(64), nullable=False)

    message: Mapped["Message"] = relationship("Message", back_populates="reactions")