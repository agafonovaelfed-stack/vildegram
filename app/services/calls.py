import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.call import Call, CallParticipant
from app.repositories.calls import CallRepository
from app.repositories.chats import ChatRepository


class CallError(Exception):
    pass


class CallNotFound(CallError):
    pass


class NotAllowed(CallError):
    pass


class CallService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.calls = CallRepository(db)
        self.chats = ChatRepository(db)

    async def get(self, call_id: uuid.UUID) -> Call:
        call = await self.calls.get_by_id(call_id)
        if call is None:
            raise CallNotFound("Call not found")
        return call

    async def start(
        self,
        *,
        initiator_id: uuid.UUID,
        kind: str = "audio",
        chat_id: uuid.UUID | None = None,
        peer_id: uuid.UUID | None = None,
    ) -> Call:
        peer_ids: list[uuid.UUID] = []

        if chat_id is not None:
            if not await self.chats.is_member(chat_id, initiator_id):
                raise NotAllowed("You are not a member of this chat")
            peer_ids = await self.chats.member_ids(chat_id)
        elif peer_id is not None:
            peer_ids = [peer_id]
        else:
            raise CallError("Either chat_id or peer_id is required")

        call = await self.calls.create(
            initiator_id=initiator_id,
            kind=kind,
            chat_id=chat_id,
            peer_ids=peer_ids,
        )
        await self.db.commit()
        await self.db.refresh(call)
        return call

    async def accept(self, *, call_id: uuid.UUID, user_id: uuid.UUID) -> Call:
        call = await self.get(call_id)
        if call.status in {"ended", "declined", "missed", "failed"}:
            raise NotAllowed("Call is already finished")

        await self.calls.set_participant_state(call_id, user_id, state="joined")

        # Первый, кто присоединился (кроме инициатора) — активируем звонок
        if call.status == "ringing":
            call.status = "active"
            call.started_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(call)
        return call

    async def decline(self, *, call_id: uuid.UUID, user_id: uuid.UUID) -> Call:
        call = await self.get(call_id)
        await self.calls.set_participant_state(call_id, user_id, state="declined")

        # Если отклонил единственный приглашённый и никто не joined — звонок missed
        joined_count = sum(1 for p in call.participants if p.state == "joined")
        if joined_count == 0 and call.status == "ringing":
            await self.calls.end_call(call, reason="rejected", status="missed")

        await self.db.commit()
        await self.db.refresh(call)
        return call

    async def leave(self, *, call_id: uuid.UUID, user_id: uuid.UUID) -> Call:
        call = await self.get(call_id)
        await self.calls.set_participant_state(call_id, user_id, state="left")

        # Если никто больше не joined — завершаем
        joined = [
            p
            for p in call.participants
            if p.state == "joined" and p.user_id != user_id
        ]
        if not joined and call.status in {"ringing", "active"}:
            await self.calls.end_call(call, reason="hangup", status="ended")

        await self.db.commit()
        await self.db.refresh(call)
        return call

    async def end(self, *, call_id: uuid.UUID, user_id: uuid.UUID) -> Call:
        """Полное завершение звонка инициатором/участником (kill-switch)."""
        call = await self.get(call_id)
        if call.initiator_id != user_id:
            p = await self.calls.get_participant(call_id, user_id)
            if p is None:
                raise NotAllowed("You are not a participant of this call")
        await self.calls.end_call(call, reason="hangup", status="ended")
        await self.db.commit()
        await self.db.refresh(call)
        return call

    async def update_participant(
        self,
        *,
        call_id: uuid.UUID,
        user_id: uuid.UUID,
        is_muted: bool | None = None,
        is_video_on: bool | None = None,
        is_screen_sharing: bool | None = None,
    ) -> CallParticipant | None:
        fields = {}
        if is_muted is not None:
            fields["is_muted"] = is_muted
        if is_video_on is not None:
            fields["is_video_on"] = is_video_on
        if is_screen_sharing is not None:
            fields["is_screen_sharing"] = is_screen_sharing

        p = await self.calls.set_participant_state(
            call_id, user_id, state="joined", **fields
        )
        await self.db.commit()
        return p

    async def history(
        self, user_id: uuid.UUID, *, limit: int = 50
    ) -> list[Call]:
        return await self.calls.list_history(user_id, limit=limit)

    def ice_servers(self) -> list[dict]:
        """Возвращает список STUN/TURN серверов для WebRTC."""
        servers: list[dict] = []
        if settings.STUN_URL:
            servers.append({"urls": [settings.STUN_URL]})
        if settings.TURN_URL:
            servers.append(
                {
                    "urls": [settings.TURN_URL],
                    "username": settings.TURN_USER,
                    "credential": settings.TURN_PASS,
                }
            )
        return servers