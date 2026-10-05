import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.badge import Badge
from app.models.privacy import PrivacySettings
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone == phone)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def exists_username(self, username: str) -> bool:
        stmt = select(User.id).where(func.lower(User.username) == username.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def exists_email(self, email: str) -> bool:
        stmt = select(User.id).where(func.lower(User.email) == email.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def create(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        password_hash: str,
        phone: str | None = None,
    ) -> User:
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            phone=phone,
        )
        self.db.add(user)
        await self.db.flush()

        # Дефолтные настройки приватности
        self.db.add(PrivacySettings(user_id=user.id))
        await self.db.flush()

        return user

    async def update(self, user: User, **fields) -> User:
        for key, value in fields.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        await self.db.flush()
        return user

    async def set_online(self, user_id: uuid.UUID, is_online: bool) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            return
        user.is_online = is_online
        user.last_seen = datetime.now(timezone.utc)
        await self.db.flush()

    async def search(self, query: str, *, exclude_id: uuid.UUID, limit: int = 20) -> list[User]:
        pattern = f"%{query.lower()}%"
        stmt = (
            select(User)
            .where(User.id != exclude_id)
            .where(User.is_active.is_(True))
            .where(
                or_(
                    func.lower(User.username).like(pattern),
                    func.lower(User.display_name).like(pattern),
                )
            )
            .order_by(User.is_online.desc(), User.username.asc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_user_badges(self, user_id: uuid.UUID) -> list[Badge]:
        stmt = select(Badge).where(Badge.user_id == user_id).order_by(Badge.created_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_badges_for_users(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[Badge]]:
        """Батч-загрузка меток для списка юзеров — чтобы не делать N+1."""
        if not user_ids:
            return {}
        stmt = select(Badge).where(Badge.user_id.in_(user_ids)).order_by(Badge.created_at.asc())
        badges = (await self.db.execute(stmt)).scalars().all()
        result: dict[uuid.UUID, list[Badge]] = {uid: [] for uid in user_ids}
        for b in badges:
            result.setdefault(b.user_id, []).append(b)
        return result