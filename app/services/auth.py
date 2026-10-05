import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.session import UserSession
from app.services.email import send_login_code
from app.models.user import User
from app.repositories.users import UserRepository


class AuthError(Exception):
    """Общая ошибка аутентификации."""


_email_codes: dict[str, tuple[str, datetime]] = {}


def _email_key(email: str) -> str:
    return email.strip().lower()


def _base_username(email: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_]", "_", email.split("@", 1)[0]).strip("_")
    return (raw or "user")[:24]


class UsernameTaken(AuthError):
    pass


class EmailTaken(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)


    async def request_email_code(self, email: str) -> str:
        key = _email_key(email)
        now = datetime.now(timezone.utc)
        existing = _email_codes.get(key)
        if existing and (now - existing[1]).total_seconds() < 45:
            raise AuthError("Подождите 45 секунд перед повторной отправкой кода")
        code = f"{secrets.randbelow(1_000_000):06d}"
        _email_codes[key] = (code, now)
        try:
            await send_login_code(key, code)
        except Exception:
            _email_codes.pop(key, None)
            raise
        return code

    async def verify_email_code(
        self, *, email: str, code: str, user_agent: str | None = None, ip_address: str | None = None
    ) -> tuple[User, str, str]:
        key = _email_key(email)
        saved = _email_codes.get(key)
        if not saved:
            raise InvalidCredentials("Код не найден или срок его действия истёк")
        saved_code, created_at = saved
        if (datetime.now(timezone.utc) - created_at).total_seconds() > 600:
            _email_codes.pop(key, None)
            raise InvalidCredentials("Срок действия кода истёк")
        if not secrets.compare_digest(saved_code, code):
            raise InvalidCredentials("Неверный код")

        _email_codes.pop(key, None)
        user = await self.users.get_by_email(key)
        if user is None:
            base = _base_username(key)
            username = base
            suffix = 1
            while await self.users.exists_username(username):
                suffix += 1
                username = f"{base[:(32-len(str(suffix))-1)]}_{suffix}"
            display_name = key.split("@", 1)[0][:64] or username
            user = await self.users.create(
                username=username,
                email=key,
                display_name=display_name,
                password_hash=hash_password(secrets.token_urlsafe(32)),
            )
        elif not user.is_active:
            raise InvalidCredentials("Аккаунт отключён")

        access, refresh = await self._issue_tokens(
            user, user_agent=user_agent, ip_address=ip_address
        )
        await self.db.commit()
        return user, access, refresh

    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        display_name: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str, str]:
        if await self.users.exists_username(username):
            raise UsernameTaken("Username already taken")
        if await self.users.exists_email(email):
            raise EmailTaken("Email already taken")

        user = await self.users.create(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
        )

        access, refresh = await self._issue_tokens(
            user, user_agent=user_agent, ip_address=ip_address
        )
        await self.db.commit()
        return user, access, refresh

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str, str]:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentials("Invalid email or password")
        if not user.is_active:
            raise InvalidCredentials("Account is disabled")

        access, refresh = await self._issue_tokens(
            user, user_agent=user_agent, ip_address=ip_address
        )
        await self.db.commit()
        return user, access, refresh

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            user_id = uuid.UUID(payload["sub"])
        except Exception as e:
            raise InvalidCredentials("Invalid refresh token") from e

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidCredentials("User not found")

        access = create_access_token(str(user.id))
        new_refresh = create_refresh_token(str(user.id))
        await self.db.commit()
        return access, new_refresh

    async def logout(self, user_id: uuid.UUID) -> None:
        """Отзывает все активные refresh-сессии пользователя."""
        from sqlalchemy import update

        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .where(UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def _issue_tokens(
        self,
        user: User,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[str, str]:
        access = create_access_token(str(user.id))
        refresh = create_refresh_token(str(user.id))

        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_password(refresh),
            user_agent=(user_agent or "")[:255] or None,
            ip_address=(ip_address or "")[:64] or None,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(session)
        await self.db.flush()
        return access, refresh