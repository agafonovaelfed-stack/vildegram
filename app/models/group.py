import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    """Группа (отдельно от Chat — расширение с правами и настройками)."""

    __tablename__ = "groups"

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

    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    # Права по умолчанию
    members_can_send: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    members_can_invite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    members_can_pin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    members_can_change_info: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    member_count: Mapped[int] = mapped_column(default=0, nullable=False)

    members: Mapped[list["GroupMember"]] = relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # owner | admin | member
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)

    # Индивидуальные разрешения поверх роли
    can_send_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_send_media: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_invite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_pin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    group: Mapped["Group"] = relationship("Group", back_populates="members")