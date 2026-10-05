import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.models.privacy import PrivacySettings
from app.schemas.user import (
    BadgeOut,
    UserMe,
    UserPublic,
    UserSearchResult,
    UserUpdate,
    PrivacySettingsOut,
    PrivacySettingsUpdate,
)
from app.services.badges import BadgeService
from app.services.users import UserNotFound, UserService

router = APIRouter(prefix="/users", tags=["users"])


_PRIVACY_CHOICES = {"everyone", "contacts", "nobody"}


def _validate_privacy_value(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if value not in _PRIVACY_CHOICES:
        raise HTTPException(status_code=422, detail=f"Invalid privacy value for {field}")
    return value


@router.get("/me/privacy", response_model=PrivacySettingsOut)
async def get_privacy(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> PrivacySettingsOut:
    settings = (await db.execute(select(PrivacySettings).where(PrivacySettings.user_id == current.id))).scalar_one_or_none()
    if settings is None:
        settings = PrivacySettings(user_id=current.id)
        db.add(settings)
        await db.flush()
    return PrivacySettingsOut.model_validate(settings)


@router.patch("/me/privacy", response_model=PrivacySettingsOut)
async def update_privacy(
    data: PrivacySettingsUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> PrivacySettingsOut:
    settings = (await db.execute(select(PrivacySettings).where(PrivacySettings.user_id == current.id))).scalar_one_or_none()
    if settings is None:
        settings = PrivacySettings(user_id=current.id)
        db.add(settings)
        await db.flush()

    values = data.model_dump(exclude_unset=True)
    for field in ("show_last_seen", "show_online", "show_avatar", "show_phone", "allow_messages", "allow_calls", "allow_groups"):
        if field in values:
            setattr(settings, field, _validate_privacy_value(values[field], field))
    for field in ("allow_read_receipts", "allow_typing_indicator"):
        if field in values:
            setattr(settings, field, values[field])
    await db.flush()
    return PrivacySettingsOut.model_validate(settings)


@router.get("/me", response_model=UserMe)
async def me(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> UserMe:
    badges = await BadgeService(db).list_for_user(current.id)
    data = UserMe.model_validate(current)
    data.badges = [BadgeOut.model_validate(b) for b in badges]
    return data


@router.patch("/me", response_model=UserMe)
async def update_me(
    data: UserUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> UserMe:
    service = UserService(db)
    updated = await service.update_profile(
        current,
        display_name=data.display_name,
        bio=data.bio,
        avatar_url=data.avatar_url,
        phone=data.phone,
    )
    badges = await BadgeService(db).list_for_user(updated.id)
    result = UserMe.model_validate(updated)
    result.badges = [BadgeOut.model_validate(b) for b in badges]
    return result


@router.get("/search", response_model=list[UserSearchResult])
async def search(
    q: str = Query(min_length=1, max_length=32),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[UserSearchResult]:
    users = await UserService(db).search(q, exclude_id=current.id)
    if not users:
        return []

    badge_map = await BadgeService(db).badges_for_many([u.id for u in users])

    result: list[UserSearchResult] = []
    for u in users:
        item = UserSearchResult.model_validate(u)
        item.badges = [BadgeOut.model_validate(b) for b in badge_map.get(u.id, [])]
        result.append(item)
    return result


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: uuid.UUID,
    _current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> UserPublic:
    try:
        user = await UserService(db).get(user_id)
    except UserNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    badges = await BadgeService(db).list_for_user(user.id)
    result = UserPublic.model_validate(user)
    result.badges = [BadgeOut.model_validate(b) for b in badges]
    return result


@router.get("/by-username/{username}", response_model=UserPublic)
async def get_user_by_username(
    username: str,
    _current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> UserPublic:
    try:
        user = await UserService(db).get_by_username(username)
    except UserNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    badges = await BadgeService(db).list_for_user(user.id)
    result = UserPublic.model_validate(user)
    result.badges = [BadgeOut.model_validate(b) for b in badges]
    return result