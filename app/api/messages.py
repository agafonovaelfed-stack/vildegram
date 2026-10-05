import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.message import (
    MessageOut,
    MessageUpdate,
    ReactionCreate,
    ReadReceiptIn,
)
from app.services.messages import (
    EmptyMessage,
    MessageNotFound,
    MessageService,
    NotAMember,
    NotAuthor,
)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.patch("/{message_id}", response_model=MessageOut)
async def edit_message(
    message_id: uuid.UUID,
    data: MessageUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MessageOut:
    service = MessageService(db)
    try:
        msg = await service.edit(
            message_id=message_id, user_id=current.id, text=data.text
        )
    except MessageNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAuthor as e:
        raise HTTPException(status_code=403, detail=str(e))
    except EmptyMessage as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MessageOut.model_validate(msg)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = MessageService(db)
    try:
        await service.delete(message_id=message_id, user_id=current.id)
    except MessageNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAuthor as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{message_id}/reactions", status_code=status.HTTP_204_NO_CONTENT)
async def add_reaction(
    message_id: uuid.UUID,
    data: ReactionCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = MessageService(db)
    try:
        info = await service.add_reaction(
            message_id=message_id, user_id=current.id, emoji=data.emoji
        )
        # Broadcast в комнату чата, чтобы все видели реакцию мгновенно
        from app.sockets.namespace import sio
        await sio.emit("message:reaction", {
            "action": "add",
            "chat_id": info["chat_id"],
            "message_id": info["message_id"],
            "user_id": info["user_id"],
            "emoji": info["emoji"],
        }, room=f"chat:{info['chat_id']}")
    except MessageNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{message_id}/reactions", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(
    message_id: uuid.UUID,
    emoji: str,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = MessageService(db)
    try:
        info = await service.remove_reaction(
            message_id=message_id, user_id=current.id, emoji=emoji
        )
        from app.sockets.namespace import sio
        await sio.emit("message:reaction", {
            "action": "remove",
            "chat_id": info["chat_id"],
            "message_id": info["message_id"],
            "user_id": info["user_id"],
            "emoji": info["emoji"],
        }, room=f"chat:{info['chat_id']}")
    except MessageNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    data: ReadReceiptIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = MessageService(db)
    try:
        await service.mark_read(
            chat_id=data.chat_id,
            user_id=current.id,
            last_message_id=data.last_read_message_id,
        )
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))