import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminLog(Base):
    """Лог действий администраторов.

    action:
      - badge.issue    — выдача метки
      - badge.revoke   — снятие метки
      - user.ban       — бан
      - user.unban     — разбан
      - report.resolve — закрытие жалобы
      - channel.delete — удаление канала
      - group.delete   — удаление группы
      - settings.update — изменение настроек
    """

    __tablename__ = "admin_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # К чему применено
    target_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Дополнительные данные: причина, старая/новая роль, метка и т.д.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )