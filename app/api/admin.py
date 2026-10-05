import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin import (
    AdminLogOut,
    ReportOut,
    ReportResolve,
    StatsOut,
    UserBanIn,
)
from app.schemas.badge import BadgeCreate, BadgeOut
from app.services.badges import (
    BadgeNotFound,
    BadgeService,
    CannotRevoke,
    InvalidBadgeKind,
    NotAuthorized,
)
from app.services.moderation import (
    InvalidReport,
    ModerationError,
    ModerationService,
    ReportNotFound,
)
from app.services.users import UserNotFound, UserService

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Пускает только тех, у кого есть метка 'v'."""
    has_v = await BadgeService(db).has_badge(current.id, "v")
    if not has_v:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required (badge 'v')",
        )
    return current


# ---- Badges ----


@router.post("/badges", response_model=BadgeOut, status_code=status.HTTP_201_CREATED)
async def issue_badge(
    data: BadgeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> BadgeOut:
    service = BadgeService(db)
    try:
        badge = await service.issue(
            target_user_id=data.user_id,
            kind=data.kind,
            issued_by=admin.id,
            reason=data.reason,
        )
    except InvalidBadgeKind as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BadgeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return BadgeOut.model_validate(badge)


@router.delete("/badges/{badge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_badge(
    badge_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = BadgeService(db)
    try:
        await service.revoke(badge_id=badge_id, revoked_by=admin.id)
    except BadgeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (CannotRevoke, NotAuthorized) as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---- Users ----


@router.post("/users/{user_id}/ban", status_code=status.HTTP_204_NO_CONTENT)
async def ban_user(
    user_id: uuid.UUID,
    data: UserBanIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = ModerationService(db)
    try:
        await service.ban_user(admin_id=admin.id, target_id=user_id, reason=data.reason)
    except ModerationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/users/{user_id}/unban", status_code=status.HTTP_204_NO_CONTENT)
async def unban_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = ModerationService(db)
    try:
        await service.unban_user(admin_id=admin.id, target_id=user_id)
    except ModerationError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- Reports ----


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    status_filter: str | None = None,
    limit: int = 100,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> list[ReportOut]:
    service = ModerationService(db)
    reports = await service.list_reports(status=status_filter, limit=limit)
    return [ReportOut.model_validate(r) for r in reports]


@router.post("/reports/{report_id}/resolve", response_model=ReportOut)
async def resolve_report(
    report_id: uuid.UUID,
    data: ReportResolve,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> ReportOut:
    service = ModerationService(db)
    try:
        report = await service.resolve_report(
            report_id=report_id,
            admin_id=admin.id,
            status=data.status,
            resolution_note=data.resolution_note,
        )
    except ReportNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidReport as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReportOut.model_validate(report)


# ---- Stats ----


@router.get("/stats", response_model=StatsOut)
async def stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> StatsOut:
    service = ModerationService(db)
    data = await service.stats()
    return StatsOut(**data)