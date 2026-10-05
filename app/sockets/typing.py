from app.sockets.namespace import get_user_id, sio


@sio.event
async def typing_start(sid: str, data: dict) -> None:
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    if not user_id or not chat_id:
        return
    await sio.emit(
        "typing:start",
        {"user_id": user_id, "chat_id": chat_id},
        room=f"chat:{chat_id}",
        skip_sid=sid,
    )


@sio.event
async def typing_stop(sid: str, data: dict) -> None:
    user_id = get_user_id(sid)
    chat_id = (data or {}).get("chat_id")
    if not user_id or not chat_id:
        return
    await sio.emit(
        "typing:stop",
        {"user_id": user_id, "chat_id": chat_id},
        room=f"chat:{chat_id}",
        skip_sid=sid,
    )