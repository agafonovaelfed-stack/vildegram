from typing import Any

import socketio

from app.core.config import settings
from app.sockets.auth import SocketAuthError, extract_token, user_id_from_token

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list,
    logger=settings.DEBUG,
    engineio_logger=False,
)

# sid -> user_id (кто подключён)
_sid_to_user: dict[str, str] = {}
# user_id -> set[sid] (у одного юзера может быть несколько вкладок)
_user_to_sids: dict[str, set[str]] = {}


def get_user_id(sid: str) -> str | None:
    return _sid_to_user.get(sid)


def sids_for_user(user_id: str) -> set[str]:
    return _user_to_sids.get(user_id, set())


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None) -> None:
    token = extract_token(auth, environ)
    try:
        user_id = str(user_id_from_token(token))
    except SocketAuthError as e:
        raise socketio.exceptions.ConnectionRefusedError(str(e)) from e

    _sid_to_user[sid] = user_id
    _user_to_sids.setdefault(user_id, set()).add(sid)

    await sio.enter_room(sid, f"user:{user_id}")

    # Импортируем здесь, чтобы не было циклического импорта
    from app.sockets import presence
    await presence.on_connect(sid, user_id)


@sio.event
async def disconnect(sid: str, reason: str | None = None) -> None:
    user_id = _sid_to_user.pop(sid, None)
    if user_id is not None:
        bucket = _user_to_sids.get(user_id)
        if bucket is not None:
            bucket.discard(sid)
            if not bucket:
                _user_to_sids.pop(user_id, None)

    # Отключаем из звонков
    from app.signaling.manager import signaling_manager
    call_id = signaling_manager.call_id_for_sid(sid)
    if call_id is not None and user_id is not None:
        from app.sockets import calls as calls_events
        await calls_events.handle_sid_disconnect(
            sid=sid, user_id=user_id, call_id=call_id
        )

    if user_id is not None:
        from app.sockets import presence
        await presence.on_disconnect(sid, user_id)


@sio.event
async def ping(sid: str, data: Any = None) -> dict:
    return {"pong": True}


# ----------------------------------------------------------------------------
# Регистрация обработчиков из соседних модулей.
#
# Импорты в конце файла — чтобы избежать циклической зависимости:
# эти модули импортируют `sio` из этого же файла, поэтому если импортировать
# их в шапке, будет ImportError. Декораторы @sio.event сработают при импорте.
# ----------------------------------------------------------------------------
from app.sockets import calls as _calls  # noqa: E402, F401
from app.sockets import chat_events as _chat_events  # noqa: E402, F401
from app.sockets import typing as _typing  # noqa: E402, F401

# presence.py не содержит @sio.event (только функции, вызываемые из connect/disconnect),
# но импортируем для единообразия и чтобы убедиться, что модуль рабочий.
from app.sockets import presence as _presence  # noqa: E402, F401
from app.sockets import notifications as _notifications  # noqa: E402, F401