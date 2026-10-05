import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin import ReportCreate, ReportOut
from app.services.moderation import (
    InvalidReport,
    ModerationService,
    ReportNotFound,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    data: ReportCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ReportOut:
    service = ModerationService(db)
    try:
        report = await service.create_report(
            reporter_id=current.id,
            target_type=data.target_type,
            target_id=data.target_id,
            reason=data.reason,
            comment=data.comment,
        )
    except InvalidReport as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReportOut.model_validate(report)


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: uuid.UUID,
    _current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ReportOut:
    service = ModerationService(db)
    try:
        report = await service.get_report(report_id)
    except ReportNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ReportOut.model_validate(report)