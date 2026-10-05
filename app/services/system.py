"""Официальный системный чат VildeGram."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.badge import Badge
from app.models.chat import Chat, ChatMember
from app.models.message import Message
from app.models.user import User


SYSTEM_USERNAME = "vildegram"
SYSTEM_EMAIL = "system@vildegram.local"
SYSTEM_DISPLAY_NAME = "VildeGram"
SYSTEM_PASSWORD = "system-account-no-login-" + uuid.uuid4().hex

SYSTEM_BIO = " ".join([
    "Официальный аккаунт VildeGram.",
    "Уведомления, безопасность, обновления.",
])

WELCOME_INTRO = " ".join([
    "Добро пожаловать в VildeGram,",
])

WELCOME_BODY = "\n\n".join([
    "Здесь будут появляться важные уведомления:",
    "- об обновлениях приложения",
    "- о входе в аккаунт с новых устройств",
    "- коды подтверждения и безопасность",
    "",
    "Если есть вопросы — напишите в этот чат.",
])

LOGIN_HINT = "Если это были не вы — смените пароль немедленно."


class SystemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_system_user(self) -> User:
        stmt = select(User).where(User.username == SYSTEM_USERNAME)
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if user is not None:
            return user

        user = User(
            username=SYSTEM_USERNAME,
            email=SYSTEM_EMAIL,
            display_name=SYSTEM_DISPLAY_NAME,
            bio=SYSTEM_BIO,
            password_hash=hash_password(SYSTEM_PASSWORD),
            is_active=True,
            is_bot=True,
        )
        self.db.add(user)
        await self.db.flush()

        self.db.add(Badge(
            user_id=user.id,
            kind="v",
            revocable=False,
            reason="System account",
        ))
        await self.db.flush()
        return user

    async def ensure_chat_for(self, user_id: uuid.UUID) -> Chat:
        system_user = await self.ensure_system_user()

        sub = (
            select(ChatMember.chat_id)
            .where(ChatMember.user_id.in_([user_id, system_user.id]))
            .group_by(ChatMember.chat_id)
        )
        candidate_ids = [row[0] for row in (await self.db.execute(sub)).all()]
        if candidate_ids:
            stmt = (
                select(Chat)
                .where(Chat.id.in_(candidate_ids))
                .where(Chat.kind == "direct")
                .where(Chat.is_service.is_(True))
                .limit(1)
            )
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                return existing

        chat = Chat(
            kind="direct",
            created_by=system_user.id,
            title=SYSTEM_DISPLAY_NAME,
            is_service=True,
        )
        self.db.add(chat)
        await self.db.flush()

        self.db.add_all([
            ChatMember(chat_id=chat.id, user_id=system_user.id, role="owner"),
            ChatMember(chat_id=chat.id, user_id=user_id, role="member"),
        ])
        await self.db.flush()
        return chat

    async def notify(
        self,
        user_id: uuid.UUID,
        text: str,
        *,
        kind: str = "system",
    ) -> Message:
        system_user = await self.ensure_system_user()
        chat = await self.ensure_chat_for(user_id)

        msg = Message(
            chat_id=chat.id,
            sender_id=system_user.id,
            text=text,
            kind=kind,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def notify_welcome(self, user_id: uuid.UUID, display_name: str) -> Message:
        text = WELCOME_INTRO + " " + display_name + "!\n\n" + WELCOME_BODY
        return await self.notify(user_id, text, kind="system")


    async def notify_code(self, user_id: uuid.UUID, code: str, *, purpose: str = "подтверждения") -> Message:
        return await self.notify(
            user_id,
            f"Код {purpose} VildeGram\n\n{code}\n\nНикому не сообщайте этот код. Если вы не запрашивали его, просто проигнорируйте сообщение.",
            kind="system",
        )

    async def notify_login(
        self,
        user_id: uuid.UUID,
        device: str | None,
        ip_address: str | None = None,
    ) -> Message:
        when = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        lines = [
            "Вход в аккаунт",
            "",
            "Время: " + when,
        ]
        if device:
            lines.append("Устройство: " + device)
        if ip_address:
            lines.append("IP: " + ip_address)
        lines.append("")
        lines.append(LOGIN_HINT)
        return await self.notify(user_id, "\n".join(lines), kind="system")


async def ensure_system_on_startup(db: AsyncSession) -> None:
    service = SystemService(db)
    await service.ensure_system_user()
    await db.commit()
