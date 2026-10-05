import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReadState(Base):
    """Состояние прочтения: до какого сообщения дочитал юзер в чате.

    last_read_message_id — последнее прочитанное.
    last_read_at — время последнего прочтения (для счётчиков и «прочитано»).
    """

    __tablename__ = "read_states"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    last_read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Для каналов: последний прочитанный пост, чтобы считать непрочитанные
    unread_count: Mapped[int] = mapped_column(default=0, nullable=False)