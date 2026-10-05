import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.call import (
    CallActionIn,
    CallOut,
    CallStartIn,
    CallUpdateIn,
    IceServerOut,
)
from app.services.calls import (
    CallError,
    CallNotFound,
    CallService,
    NotAllowed,
)

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("", response_model=CallOut, status_code=status.HTTP_201_CREATED)
async def start_call(
    data: CallStartIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        call = await service.start(
            initiator_id=current.id,
            kind=data.kind,
            chat_id=data.chat_id,
            peer_id=data.peer_id,
        )
    except CallError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))

    return CallOut.model_validate(call)


@router.post("/{call_id}/accept", response_model=CallOut)
async def accept_call(
    call_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        call = await service.accept(call_id=call_id, user_id=current.id)
    except CallNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    return CallOut.model_validate(call)


@router.post("/{call_id}/decline", response_model=CallOut)
async def decline_call(
    call_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        call = await service.decline(call_id=call_id, user_id=current.id)
    except CallNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return CallOut.model_validate(call)


@router.post("/{call_id}/leave", response_model=CallOut)
async def leave_call(
    call_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        call = await service.leave(call_id=call_id, user_id=current.id)
    except CallNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return CallOut.model_validate(call)


@router.post("/{call_id}/end", response_model=CallOut)
async def end_call(
    call_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        call = await service.end(call_id=call_id, user_id=current.id)
    except CallNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    return CallOut.model_validate(call)


@router.patch("/{call_id}/me", response_model=CallOut)
async def update_participant(
    call_id: uuid.UUID,
    data: CallUpdateIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CallOut:
    service = CallService(db)
    try:
        await service.update_participant(
            call_id=call_id,
            user_id=current.id,
            is_muted=data.is_muted,
            is_video_on=data.is_video_on,
            is_screen_sharing=data.is_screen_sharing,
        )
        call = await service.get(call_id)
    except CallNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return CallOut.model_validate(call)


@router.get("", response_model=list[CallOut])
async def call_history(
    limit: int = 50,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[CallOut]:
    service = CallService(db)
    calls = await service.history(current.id, limit=limit)
    return [CallOut.model_validate(c) for c in calls]


@router.get("/ice-servers", response_model=list[IceServerOut])
async def ice_servers(
    _current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[IceServerOut]:
    service = CallService(db)
    return [IceServerOut(**s) for s in service.ice_servers()]