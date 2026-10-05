import uuid

from app.db.session import AsyncSessionLocal
from app.sockets.namespace import sio
from app.services.presence import PresenceService


async def _set_online(user_id: str, online: bool) -> None:
    async with AsyncSessionLocal() as db:
        service = PresenceService(db)
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return
        if online:
            await service.set_online(uid)
        else:
            await service.set_offline(uid)


async def on_connect(sid: str, user_id: str) -> None:
    await _set_online(user_id, True)
    # Broadcast всем, кроме себя
    await sio.emit(
        "presence:online",
        {"user_id": user_id},
        skip_sid=sid,
    )


async def on_disconnect(sid: str, user_id: str) -> None:
    # Если это была последняя вкладка — оффлайн
    from app.sockets.namespace import sids_for_user
    if not sids_for_user(user_id):
        await _set_online(user_id, False)
        await sio.emit("presence:offline", {"user_id": user_id})


async def broadcast_typing_stop(user_id: str, chat_id: str) -> None:
    await sio.emit(
        "typing:stop",
        {"user_id": user_id, "chat_id": chat_id},
        room=f"chat:{chat_id}",
    )