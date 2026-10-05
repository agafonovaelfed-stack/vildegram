import uuid

from app.db.session import AsyncSessionLocal
from app.services.calls import CallService
from app.signaling.manager import signaling_manager
from app.signaling.rooms import close_room, create_call_room, get_room
from app.sockets.namespace import get_user_id, sio


async def _get_member_ids(chat_id: str) -> list[str]:
    try:
        cid = uuid.UUID(chat_id)
    except ValueError:
        return []

    from app.repositories.chats import ChatRepository
    async with AsyncSessionLocal() as db:
        ids = await ChatRepository(db).member_ids(cid)
        return [str(u) for u in ids]


async def handle_sid_disconnect(
    *, sid: str, user_id: str, call_id: uuid.UUID
) -> None:
    room = get_room(call_id)
    if room is None:
        return
    signaling_manager.leave(call_id=call_id, user_id=uuid.UUID(user_id))
    await sio.emit(
        "call:peer-left",
        {"call_id": str(call_id), "user_id": user_id, "reason": "disconnect"},
        room=f"call:{call_id}",
    )
    if get_room(call_id) is None:
        # последний ушёл — финализируем звонок в БД
        async with AsyncSessionLocal() as db:
            service = CallService(db)
            try:
                call = await service.get(call_id)
                await service.end(call_id=call_id, user_id=call.initiator_id)
            except Exception:
                pass


@sio.event
async def call_start(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    if not user_id:
        return {"ok": False, "error": "not authenticated"}

    kind = (data or {}).get("kind", "audio")
    chat_id = (data or {}).get("chat_id")
    peer_id = (data or {}).get("peer_id")

    async with AsyncSessionLocal() as db:
        service = CallService(db)
        try:
            call = await service.start(
                initiator_id=uuid.UUID(user_id),
                kind=kind,
                chat_id=uuid.UUID(chat_id) if chat_id else None,
                peer_id=uuid.UUID(peer_id) if peer_id else None,
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}

    create_call_room(
        call_id=call.id, kind=call.kind, initiator_id=call.initiator_id
    )
    signaling_manager.join(call_id=call.id, user_id=uuid.UUID(user_id), sid=sid)
    await sio.enter_room(sid, f"call:{call.id}")

    # Приглашаем участников
    targets: list[str] = []
    if chat_id:
        targets = await _get_member_ids(chat_id)
    elif peer_id:
        targets = [peer_id]

    for target in targets:
        if target == user_id:
            continue
        await sio.emit(
            "call:incoming",
            {
                "call_id": str(call.id),
                "kind": call.kind,
                "from_user_id": user_id,
                "chat_id": chat_id,
            },
            room=f"user:{target}",
        )

    return {"ok": True, "call_id": str(call.id)}


@sio.event
async def call_accept(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    if not user_id or not call_id_raw:
        return {"ok": False, "error": "call_id required"}

    call_id = uuid.UUID(call_id_raw)

    async with AsyncSessionLocal() as db:
        service = CallService(db)
        try:
            await service.accept(call_id=call_id, user_id=uuid.UUID(user_id))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    signaling_manager.join(call_id=call_id, user_id=uuid.UUID(user_id), sid=sid)
    await sio.enter_room(sid, f"call:{call_id}")
    await sio.emit(
        "call:peer-joined",
        {"call_id": str(call_id), "user_id": user_id},
        room=f"call:{call_id}",
        skip_sid=sid,
    )
    return {"ok": True, "call_id": str(call_id)}


@sio.event
async def call_decline(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    if not user_id or not call_id_raw:
        return {"ok": False, "error": "call_id required"}

    call_id = uuid.UUID(call_id_raw)

    async with AsyncSessionLocal() as db:
        service = CallService(db)
        try:
            await service.decline(call_id=call_id, user_id=uuid.UUID(user_id))
        except Exception:
            pass

    await sio.emit(
        "call:peer-declined",
        {"call_id": str(call_id), "user_id": user_id},
        room=f"call:{call_id}",
        skip_sid=sid,
    )
    return {"ok": True}


@sio.event
async def call_leave(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    if not user_id or not call_id_raw:
        return {"ok": False, "error": "call_id required"}

    call_id = uuid.UUID(call_id_raw)
    signaling_manager.leave(call_id=call_id, user_id=uuid.UUID(user_id))
    await sio.leave_room(sid, f"call:{call_id}")

    async with AsyncSessionLocal() as db:
        service = CallService(db)
        try:
            await service.leave(call_id=call_id, user_id=uuid.UUID(user_id))
        except Exception:
            pass

    await sio.emit(
        "call:peer-left",
        {"call_id": str(call_id), "user_id": user_id, "reason": "hangup"},
        room=f"call:{call_id}",
    )

    if get_room(call_id) is None:
        close_room(call_id)
    return {"ok": True}


@sio.event
async def call_offer(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    sdp = (data or {}).get("sdp")
    to_user = (data or {}).get("to_user_id")
    if not user_id or not call_id_raw or not sdp:
        return {"ok": False, "error": "call_id and sdp required"}

    payload = {
        "call_id": str(call_id_raw),
        "from_user_id": user_id,
        "sdp": sdp,
        "type": "offer",
    }

    if to_user:
        await sio.emit("call:offer", payload, room=f"user:{to_user}")
    else:
        await sio.emit(
            "call:offer", payload, room=f"call:{call_id_raw}", skip_sid=sid
        )
    return {"ok": True}


@sio.event
async def call_answer(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    sdp = (data or {}).get("sdp")
    to_user = (data or {}).get("to_user_id")
    if not user_id or not call_id_raw or not sdp:
        return {"ok": False, "error": "call_id and sdp required"}

    payload = {
        "call_id": str(call_id_raw),
        "from_user_id": user_id,
        "sdp": sdp,
        "type": "answer",
    }

    if to_user:
        await sio.emit("call:answer", payload, room=f"user:{to_user}")
    else:
        await sio.emit(
            "call:answer", payload, room=f"call:{call_id_raw}", skip_sid=sid
        )
    return {"ok": True}


@sio.event
async def call_ice(sid: str, data: dict) -> dict:
    user_id = get_user_id(sid)
    call_id_raw = (data or {}).get("call_id")
    candidate = (data or {}).get("candidate")
    to_user = (data or {}).get("to_user_id")
    if not user_id or not call_id_raw or not candidate:
        return {"ok": False, "error": "call_id and candidate required"}

    payload = {
        "call_id": str(call_id_raw),
        "from_user_id": user_id,
        "candidate": candidate,
        "sdpMid": (data or {}).get("sdpMid"),
        "sdpMLineIndex": (data or {}).get("sdpMLineIndex"),
    }

    if to_user:
        await sio.emit("call:ice", payload, room=f"user:{to_user}")
    else:
        await sio.emit(
            "call:ice", payload, room=f"call:{call_id_raw}", skip_sid=sid
        )
    return {"ok": True}