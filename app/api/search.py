from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.chat import ChatOut
from app.schemas.user import BadgeOut, UserSearchResult
from app.services.badges import BadgeService
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/users", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=1, max_length=32),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[UserSearchResult]:
    service = SearchService(db)
    users = await service.users(q, exclude_id=current.id)
    if not users:
        return []
    badge_map = await BadgeService(db).badges_for_many([u.id for u in users])
    result: list[UserSearchResult] = []
    for u in users:
        item = UserSearchResult.model_validate(u)
        item.badges = [BadgeOut.model_validate(b) for b in badge_map.get(u.id, [])]
        result.append(item)
    return result


@router.get("/chats", response_model=list[ChatOut])
async def search_chats(
    q: str = Query(min_length=1, max_length=32),
    _current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ChatOut]:
    service = SearchService(db)
    chats = await service.chats(q)
    return [ChatOut.model_validate(c) for c in chats]


@router.get("")
async def global_search(
    q: str = Query(min_length=1, max_length=32),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    service = SearchService(db)
    data = await service.global_search(q, exclude_id=current.id)

    badge_map = await BadgeService(db).badges_for_many(
        [u.id for u in data["users"]]
    )
    users_out = []
    for u in data["users"]:
        item = UserSearchResult.model_validate(u)
        item.badges = [BadgeOut.model_validate(b) for b in badge_map.get(u.id, [])]
        users_out.append(item)

    return {
        "users": users_out,
        "chats": [ChatOut.model_validate(c) for c in data["chats"]],
    }