import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMember
from app.sockets.namespace import get_user_id, sio


async def _is_member(chat_id: str, user_id: str) -> bool:
    try:
        cid = uuid.UUID(chat_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        return False

    async with AsyncSessionLocal() as db:
        stmt = select(ChatMember).where(
            ChatMember.chat_id == cid, ChatMember.user_id == uid
        )
        return (await db.execute(stmt)).scalar_one_or_none() is not None


@sio.event
async def chat_join(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    if not user_id or not chat_id:
        return {"ok": False, "error": "chat_id required"}
    if not await _is_member(chat_id, user_id):
        return {"ok": False, "error": "not a member"}

    await sio.enter_room(sid, f"chat:{chat_id}")
    return {"ok": True, "chat_id": chat_id}


@sio.event
async def chat_leave(sid: str, data: dict) -> dict:
    chat_id = (data or {}).get("chat_id")
    if not chat_id:
        return {"ok": False, "error": "chat_id required"}
    await sio.leave_room(sid, f"chat:{chat_id}")
    return {"ok": True}


@sio.event
async def message_send(sid: str, data: dict) -> dict:
    """Клиент отправил сообщение через сокет.

    Здесь только broadcast — запись в БД делается через REST POST /chats/{id}/messages.
    Такая схема безопаснее: серверная валидация через Pydantic, а сокет — только
    для мгновенной доставки.
    """
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    if not user_id or not chat_id:
        return {"ok": False, "error": "chat_id required"}

    await sio.emit(
        "message:new",
        data,
        room=f"chat:{chat_id}",
        skip_sid=sid,
    )
    return {"ok": True}


@sio.event
async def read_receipt(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    message_id = (data or {}).get("message_id")
    if not user_id or not chat_id or not message_id:
        return {"ok": False, "error": "chat_id and message_id required"}

    await sio.emit(
        "message:read",
        {"chat_id": chat_id, "message_id": message_id, "user_id": user_id},
        room=f"chat:{chat_id}",
        skip_sid=sid,
    )
    return {"ok": True}

# Реакции на сообщения — рассылаем всем в комнате чата
@sio.event
async def message_reaction(sid, data):
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    if not user_id or not chat_id:
        return {"ok": False, "error": "chat_id required"}

    await sio.emit(
        "message:reaction",
        data,
        room=f"chat:{chat_id}",
        skip_sid=sid,
    )
    return {"ok": True}
