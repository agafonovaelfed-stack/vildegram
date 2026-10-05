import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Badge(Base):
    """Метки VildeGram.

    kind:
      - verified: синяя галочка (подтверждённый аккаунт)
      - scam: красная метка SCAM
      - fake: метка FAKE
      - v: золотая V (админ/разработчик), выдаёт только владелец
    """

    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    kind: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # По ТЗ: метки невозможно снять обычным юзером.
    # revocable=False используется для kind='v' — снять может только владелец.
    revocable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="badges", foreign_keys=[user_id]
    )