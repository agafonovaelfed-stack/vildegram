import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.models.chat import ChatMember
from app.schemas.chat import (
    ChatCreate,
    ChatInviteIn,
    ChatMemberOut,
    ChatMemberUpdate,
    ChatOut,
    ChatUpdate,
)
from app.schemas.message import MessageCreate, MessageOut, MessagePage
from app.services.chats import (
    ChatNotFound,
    ChatService,
    NotAMember,
    NotAllowed,
)
from app.services.messages import (
    EmptyMessage,
    MessageService,
    NotAMember as MsgNotAMember,
)

router = APIRouter(prefix="/chats", tags=["chats"])


async def _chat_to_out(chat, members, current_user_id: uuid.UUID | None = None, db: AsyncSession | None = None) -> ChatOut:
    title = chat.title
    if chat.kind == "direct" and current_user_id is not None and db is not None:
        peer = (await db.execute(
            select(User).join(ChatMember, ChatMember.user_id == User.id)
            .where(ChatMember.chat_id == chat.id, ChatMember.user_id != current_user_id)
            .limit(1)
        )).scalar_one_or_none()
        if peer is not None:
            title = peer.display_name or peer.username

    return ChatOut(
        id=chat.id,
        kind=chat.kind,
        title=title,
        description=chat.description,
        avatar_url=chat.avatar_url,
        is_public=chat.is_public,
        username=chat.username,
        is_service=chat.is_service,
        created_at=chat.created_at,
        members=[ChatMemberOut.model_validate(m) for m in members],
    )


@router.get("", response_model=list[ChatOut])
async def list_chats(
    include_archived: bool = False,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ChatOut]:
    service = ChatService(db)
    pairs = await service.list_for_user(
        current.id, include_archived=include_archived
    )

    result = []
    for chat, member in pairs:
        result.append(await _chat_to_out(chat, [member], current.id, db))
    return result


@router.post("/direct", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_direct(
    peer_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    service = ChatService(db)
    try:
        chat = await service.create_direct(
            current_user_id=current.id, peer_id=peer_id
        )
    except NotAllowed as e:
        raise HTTPException(status_code=400, detail=str(e))

    member = await service.chats.get_member(chat.id, current.id)
    return await _chat_to_out(chat, [member] if member else [], current.id, db)


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(
    data: ChatCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    service = ChatService(db)

    if data.kind == "direct":
        if data.peer_id is None:
            raise HTTPException(status_code=400, detail="peer_id required for direct")
        chat = await service.create_direct(
            current_user_id=current.id, peer_id=data.peer_id
        )
    elif data.kind == "group":
        if not data.title:
            raise HTTPException(status_code=400, detail="title required for group")
        chat = await service.create_group(
            owner_id=current.id,
            title=data.title,
            description=data.description,
            is_public=data.is_public,
            username=data.username,
        )
    elif data.kind == "channel":
        if not data.title:
            raise HTTPException(status_code=400, detail="title required for channel")
        chat = await service.create_channel(
            owner_id=current.id,
            title=data.title,
            description=data.description,
            is_public=data.is_public,
            username=data.username,
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown chat kind")

    member = await service.chats.get_member(chat.id, current.id)
    return await _chat_to_out(chat, [member] if member else [], current.id, db)


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    service = ChatService(db)
    try:
        chat, member = await service.require_member(chat_id, current.id)
    except ChatNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))

    return await _chat_to_out(chat, [member], current.id, db)


@router.patch("/{chat_id}", response_model=ChatOut)
async def update_chat(
    chat_id: uuid.UUID,
    data: ChatUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    service = ChatService(db)
    try:
        chat = await service.update_chat(
            chat_id=chat_id,
            actor_id=current.id,
            title=data.title,
            description=data.description,
            avatar_url=data.avatar_url,
            is_public=data.is_public,
        )
    except ChatNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (NotAMember, NotAllowed) as e:
        raise HTTPException(status_code=403, detail=str(e))

    member = await service.chats.get_member(chat.id, current.id)
    return await _chat_to_out(chat, [member] if member else [], current.id, db)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = ChatService(db)
    try:
        await service.delete_chat(chat_id=chat_id, actor_id=current.id)
    except ChatNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (NotAMember, NotAllowed) as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{chat_id}/members", response_model=list[ChatMemberOut])
async def add_members(
    chat_id: uuid.UUID,
    data: ChatInviteIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ChatMemberOut]:
    service = ChatService(db)
    try:
        added = await service.add_members(
            chat_id=chat_id, actor_id=current.id, user_ids=data.user_ids
        )
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    return [ChatMemberOut.model_validate(m) for m in added]


@router.delete(
    "/{chat_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = ChatService(db)
    try:
        await service.remove_member(
            chat_id=chat_id, actor_id=current.id, target_id=user_id
        )
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/{chat_id}/me", response_model=ChatMemberOut)
async def update_my_settings(
    chat_id: uuid.UUID,
    data: ChatMemberUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ChatMemberOut:
    service = ChatService(db)
    try:
        member = await service.update_member_settings(
            chat_id=chat_id,
            actor_id=current.id,
            is_pinned=data.is_pinned,
            is_archived=data.is_archived,
            is_muted=data.is_muted,
        )
    except NotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))
    return ChatMemberOut.model_validate(member)


@router.get("/{chat_id}/messages", response_model=MessagePage)
async def list_messages(
    chat_id: uuid.UUID,
    limit: int = 50,
    before_id: uuid.UUID | None = None,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MessagePage:
    service = MessageService(db)
    try:
        messages = await service.history(
            chat_id=chat_id,
            user_id=current.id,
            limit=limit,
            before_id=before_id,
        )
    except MsgNotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))

    items = [MessageOut.model_validate(m) for m in messages]
    next_before = items[0].id if items else None
    has_more = len(items) == limit
    return MessagePage(items=items, next_before_id=next_before, has_more=has_more)


@router.post(
    "/{chat_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    chat_id: uuid.UUID,
    data: MessageCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MessageOut:
    service = MessageService(db)
    try:
        msg = await service.send(
            chat_id=chat_id,
            sender_id=current.id,
            text=data.text,
            reply_to_id=data.reply_to_id,
            attachment_ids=data.attachment_ids,
            ttl_seconds=data.ttl_seconds,
        )
    except MsgNotAMember as e:
        raise HTTPException(status_code=403, detail=str(e))
    except EmptyMessage as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MessageOut.model_validate(msg)