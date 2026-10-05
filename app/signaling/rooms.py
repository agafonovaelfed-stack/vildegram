import uuid
from typing import Any

from app.signaling.manager import CallRoom, signaling_manager


def create_call_room(
    *,
    call_id: uuid.UUID,
    kind: str,
    initiator_id: uuid.UUID,
) -> CallRoom:
    return signaling_manager.create_room(
        call_id=call_id, kind=kind, initiator_id=initiator_id
    )


def get_room(call_id: uuid.UUID) -> CallRoom | None:
    return signaling_manager.get_room(call_id)


def close_room(call_id: uuid.UUID) -> None:
    signaling_manager.remove_room(call_id)


def peers_payload(call_id: uuid.UUID) -> list[dict[str, Any]]:
    room = signaling_manager.get_room(call_id)
    if room is None:
        return []
    return [
        {
            "user_id": str(p.user_id),
            "is_muted": p.is_muted,
            "is_video_on": p.is_video_on,
            "is_screen_sharing": p.is_screen_sharing,
        }
        for p in room.peers.values()
    ]