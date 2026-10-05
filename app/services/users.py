import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.badge import Badge
from app.models.user import User
from app.repositories.users import UserRepository


class UserError(Exception):
    pass


class UserNotFound(UserError):
    pass


class WrongPassword(UserError):
    pass


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFound("User not found")
        return user

    async def get_by_username(self, username: str) -> User:
        user = await self.users.get_by_username(username)
        if user is None:
            raise UserNotFound("User not found")
        return user

    async def search(self, query: str, *, exclude_id: uuid.UUID) -> list[User]:
        return await self.users.search(query, exclude_id=exclude_id)

    async def update_profile(
        self,
        user: User,
        *,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
        phone: str | None = None,
    ) -> User:
        fields = {}
        if display_name is not None:
            fields["display_name"] = display_name
        if bio is not None:
            fields["bio"] = bio
        if avatar_url is not None:
            fields["avatar_url"] = avatar_url
        if phone is not None:
            fields["phone"] = phone

        updated = await self.users.update(user, **fields)
        await self.db.commit()
        return updated

    async def change_password(
        self,
        user: User,
        *,
        old_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise WrongPassword("Old password is incorrect")
        user.password_hash = hash_password(new_password)
        await self.db.commit()

    async def set_online(self, user_id: uuid.UUID, is_online: bool) -> None:
        await self.users.set_online(user_id, is_online)
        await self.db.commit()

    async def badges_for(self, user_id: uuid.UUID) -> list[Badge]:
        return await self.users.get_user_badges(user_id)