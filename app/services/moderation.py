import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_log import AdminLog
from app.models.badge import Badge
from app.models.call import Call, CallParticipant
from app.models.chat import Chat
from app.models.message import Message
from app.models.report import Report
from app.models.user import User


VALID_REASONS = {"spam", "scam", "violence", "adult", "impersonation", "other"}
VALID_TARGETS = {"user", "message", "chat", "group", "channel"}
VALID_STATUSES = {"reviewed", "resolved", "dismissed"}


class ModerationError(Exception):
    pass


class InvalidReport(ModerationError):
    pass


class ReportNotFound(ModerationError):
    pass


class ModerationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_report(
        self,
        *,
        reporter_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        reason: str,
        comment: str | None = None,
    ) -> Report:
        if target_type not in VALID_TARGETS:
            raise InvalidReport(f"Unknown target_type: {target_type}")
        if reason not in VALID_REASONS:
            raise InvalidReport(f"Unknown reason: {reason}")

        report = Report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            comment=comment,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_reports(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Report]:
        stmt = select(Report)
        if status is not None:
            stmt = stmt.where(Report.status == status)
        stmt = stmt.order_by(Report.created_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_report(self, report_id: uuid.UUID) -> Report:
        report = await self.db.get(Report, report_id)
        if report is None:
            raise ReportNotFound("Report not found")
        return report

    async def resolve_report(
        self,
        *,
        report_id: uuid.UUID,
        admin_id: uuid.UUID,
        status: str,
        resolution_note: str | None = None,
    ) -> Report:
        if status not in VALID_STATUSES:
            raise InvalidReport(f"Unknown status: {status}")
        report = await self.get_report(report_id)
        report.status = status
        report.reviewed_by = admin_id
        report.reviewed_at = datetime.now(timezone.utc)
        report.resolution_note = resolution_note

        self.db.add(
            AdminLog(
                actor_id=admin_id,
                action="report.resolve",
                target_type="report",
                target_id=report_id,
                payload={"status": status},
                note=resolution_note,
            )
        )
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def ban_user(
        self,
        *,
        admin_id: uuid.UUID,
        target_id: uuid.UUID,
        reason: str | None = None,
    ) -> User:
        user = await self.db.get(User, target_id)
        if user is None:
            raise ModerationError("User not found")
        user.is_active = False
        self.db.add(
            AdminLog(
                actor_id=admin_id,
                action="user.ban",
                target_type="user",
                target_id=target_id,
                note=reason,
            )
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def unban_user(
        self,
        *,
        admin_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> User:
        user = await self.db.get(User, target_id)
        if user is None:
            raise ModerationError("User not found")
        user.is_active = True
        self.db.add(
            AdminLog(
                actor_id=admin_id,
                action="user.unban",
                target_type="user",
                target_id=target_id,
            )
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def stats(self) -> dict:
        async def scalar(stmt):
            return (await self.db.execute(stmt)).scalar() or 0

        return {
            "total_users": await scalar(select(func.count(User.id))),
            "online_users": await scalar(
                select(func.count(User.id)).where(User.is_online.is_(True))
            ),
            "total_chats": await scalar(select(func.count(Chat.id))),
            "total_messages": await scalar(
                select(func.count(Message.id)).where(Message.deleted_at.is_(None))
            ),
            "total_calls": await scalar(select(func.count(Call.id))),
            "pending_reports": await scalar(
                select(func.count(Report.id)).where(Report.status == "pending")
            ),
        }