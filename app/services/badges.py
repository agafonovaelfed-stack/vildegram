import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_log import AdminLog
from app.models.badge import Badge
from app.repositories.users import UserRepository


VALID_KINDS = {"verified", "scam", "fake", "v"}


class BadgeError(Exception):
    pass


class InvalidBadgeKind(BadgeError):
    pass


class BadgeNotFound(BadgeError):
    pass


class CannotRevoke(BadgeError):
    pass


class NotAuthorized(BadgeError):
    pass


class BadgeService:
    """Метки можно только выдать или снять через админов.

    Правила:
      - kind='v' может выдать/снять только владелец (у кого уже есть метка 'v'
        и он помечен как owner в системе). Упрощённо: кто имеет метку 'v',
        тот может выдавать любые метки; снять 'v' можно только владельческой
        операцией (см. can_issue_badge в core/permissions).
      - verified/scam/fake — выдаёт любой админ с меткой 'v'.
      - Обычный юзер не может снять метку ни с себя, ни с кого-либо.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Badge]:
        stmt = (
            select(Badge)
            .where(Badge.user_id == user_id)
            .order_by(Badge.created_at.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def badges_for_many(
        self, user_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[Badge]]:
        """Батч-загрузка меток для списка юзеров — чтобы не делать N+1."""
        if not user_ids:
            return {}
        stmt = (
            select(Badge)
            .where(Badge.user_id.in_(user_ids))
            .order_by(Badge.created_at.asc())
        )
        badges = (await self.db.execute(stmt)).scalars().all()
        result: dict[uuid.UUID, list[Badge]] = {uid: [] for uid in user_ids}
        for b in badges:
            result.setdefault(b.user_id, []).append(b)
        return result

    async def has_badge(self, user_id: uuid.UUID, kind: str) -> bool:
        stmt = select(Badge.id).where(Badge.user_id == user_id, Badge.kind == kind)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def issue(
        self,
        *,
        target_user_id: uuid.UUID,
        kind: str,
        issued_by: uuid.UUID,
        reason: str | None = None,
    ) -> Badge:
        if kind not in VALID_KINDS:
            raise InvalidBadgeKind(f"Unknown badge kind: {kind}")

        target = await self.users.get_by_id(target_user_id)
        if target is None:
            raise BadgeNotFound("Target user not found")

        if await self.has_badge(target_user_id, kind):
            # Уже есть — вернём существующий (идемпотентно)
            stmt = select(Badge).where(
                Badge.user_id == target_user_id, Badge.kind == kind
            )
            existing = (await self.db.execute(stmt)).scalar_one()
            return existing

        # 'v' — не revocable обычным способом, только владельцем
        revocable = kind != "v"

        badge = Badge(
            user_id=target_user_id,
            kind=kind,
            issued_by=issued_by,
            reason=reason,
            revocable=revocable,
        )
        self.db.add(badge)
        await self.db.flush()

        self.db.add(
            AdminLog(
                actor_id=issued_by,
                action="badge.issue",
                target_type="user",
                target_id=target_user_id,
                payload={"badge_id": str(badge.id), "kind": kind},
                note=reason,
            )
        )
        await self.db.commit()
        return badge

    async def revoke(
        self,
        *,
        badge_id: uuid.UUID,
        revoked_by: uuid.UUID,
        reason: str | None = None,
    ) -> None:
        badge = await self.db.get(Badge, badge_id)
        if badge is None:
            raise BadgeNotFound("Badge not found")

        if badge.kind == "v" and not badge.revocable:
            # 'v' снимает только владелец. Проверим, что тот, кто снимает,
            # сам имеет метку 'v' (упрощённая модель владельца).
            issuer_has_v = await self.has_badge(revoked_by, "v")
            if not issuer_has_v:
                raise NotAuthorized("Only the owner can revoke 'v' badge")

        if not badge.revocable:
            raise CannotRevoke("Badge is not revocable")

        self.db.add(
            AdminLog(
                actor_id=revoked_by,
                action="badge.revoke",
                target_type="user",
                target_id=badge.user_id,
                payload={"badge_id": str(badge.id), "kind": badge.kind},
                note=reason,
            )
        )
        await self.db.delete(badge)
        await self.db.commit()