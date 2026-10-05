import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PeerState:
    user_id: uuid.UUID
    sid: str
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_muted: bool = False
    is_video_on: bool = False
    is_screen_sharing: bool = False


@dataclass
class CallRoom:
    call_id: uuid.UUID
    kind: str
    initiator_id: uuid.UUID
    peers: dict[uuid.UUID, PeerState] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_peer(self, user_id: uuid.UUID, sid: str) -> PeerState:
        peer = PeerState(user_id=user_id, sid=sid)
        self.peers[user_id] = peer
        return peer

    def remove_peer(self, user_id: uuid.UUID) -> None:
        self.peers.pop(user_id, None)

    def is_empty(self) -> bool:
        return not self.peers

    def peer_count(self) -> int:
        return len(self.peers)


class SignalingManager:
    """In-memory реестр активных звонков.

    Для одного инстанса — ок. Для нескольких инстансов нужно синхронизировать
    через Redis pub/sub: rooms/call_id/event.
    """

    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, CallRoom] = {}
        # sid -> call_id
        self._sid_to_call: dict[str, uuid.UUID] = {}

    def create_room(
        self,
        *,
        call_id: uuid.UUID,
        kind: str,
        initiator_id: uuid.UUID,
    ) -> CallRoom:
        room = CallRoom(call_id=call_id, kind=kind, initiator_id=initiator_id)
        self._rooms[call_id] = room
        return room

    def get_room(self, call_id: uuid.UUID) -> CallRoom | None:
        return self._rooms.get(call_id)

    def remove_room(self, call_id: uuid.UUID) -> None:
        room = self._rooms.pop(call_id, None)
        if room is None:
            return
        for user_id, peer in list(room.peers.items()):
            self._sid_to_call.pop(peer.sid, None)

    def join(
        self,
        *,
        call_id: uuid.UUID,
        user_id: uuid.UUID,
        sid: str,
    ) -> PeerState | None:
        room = self._rooms.get(call_id)
        if room is None:
            return None
        peer = room.add_peer(user_id, sid)
        self._sid_to_call[sid] = call_id
        return peer

    def leave(self, *, call_id: uuid.UUID, user_id: uuid.UUID) -> None:
        room = self._rooms.get(call_id)
        if room is None:
            return
        peer = room.peers.get(user_id)
        if peer is not None:
            self._sid_to_call.pop(peer.sid, None)
        room.remove_peer(user_id)
        if room.is_empty():
            self.remove_room(call_id)

    def peers_except(
        self, *, call_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[PeerState]:
        room = self._rooms.get(call_id)
        if room is None:
            return []
        return [p for uid, p in room.peers.items() if uid != user_id]

    def call_id_for_sid(self, sid: str) -> uuid.UUID | None:
        return self._sid_to_call.get(sid)

    def all_rooms(self) -> list[CallRoom]:
        return list(self._rooms.values())


# Единственный инстанс на процесс
signaling_manager = SignalingManager()