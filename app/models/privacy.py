import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PrivacySettings(Base):
    __tablename__ = "privacy_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # everyone | contacts | nobody
    show_last_seen: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)
    show_online: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)
    show_avatar: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)
    show_phone: Mapped[str] = mapped_column(String(16), default="contacts", nullable=False)

    allow_messages: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)
    allow_calls: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)
    allow_groups: Mapped[str] = mapped_column(String(16), default="everyone", nullable=False)

    allow_read_receipts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_typing_indicator: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="privacy")