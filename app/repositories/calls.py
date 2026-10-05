import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call, CallParticipant


class CallRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, call_id: uuid.UUID) -> Call | None:
        return await self.db.get(Call, call_id)

    async def create(
        self,
        *,
        initiator_id: uuid.UUID,
        kind: str = "audio",
        chat_id: uuid.UUID | None = None,
        peer_ids: list[uuid.UUID] | None = None,
    ) -> Call:
        call = Call(
            initiator_id=initiator_id,
            kind=kind,
            chat_id=chat_id,
            status="ringing",
        )
        self.db.add(call)
        await self.db.flush()

        # Инициатор сразу joined
        self.db.add(
            CallParticipant(
                call_id=call.id,
                user_id=initiator_id,
                state="joined",
                joined_at=datetime.now(timezone.utc),
            )
        )
        # Приглашённые
        for peer_id in (peer_ids or []):
            if peer_id == initiator_id:
                continue
            self.db.add(
                CallParticipant(call_id=call.id, user_id=peer_id, state="ringing")
            )
        await self.db.flush()
        return call

    async def get_participant(
        self, call_id: uuid.UUID, user_id: uuid.UUID
    ) -> CallParticipant | None:
        stmt = select(CallParticipant).where(
            CallParticipant.call_id == call_id,
            CallParticipant.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def set_participant_state(
        self,
        call_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        state: str,
        **fields,
    ) -> CallParticipant | None:
        p = await self.get_participant(call_id, user_id)
        if p is None:
            return None
        p.state = state
        if state == "joined" and p.joined_at is None:
            p.joined_at = datetime.now(timezone.utc)
        if state == "left":
            p.left_at = datetime.now(timezone.utc)
        for key, value in fields.items():
            if hasattr(p, key) and value is not None:
                setattr(p, key, value)
        await self.db.flush()
        return p

    async def update_call(self, call: Call, **fields) -> Call:
        for key, value in fields.items():
            if hasattr(call, key) and value is not None:
                setattr(call, key, value)
        await self.db.flush()
        return call

    async def end_call(
        self,
        call: Call,
        *,
        reason: str = "hangup",
        status: str = "ended",
    ) -> Call:
        now = datetime.now(timezone.utc)
        call.status = status
        call.ended_at = now
        call.end_reason = reason
        if call.started_at is not None:
            call.duration_seconds = int((now - call.started_at).total_seconds())
        await self.db.flush()
        return call

    async def list_history(self, user_id: uuid.UUID, *, limit: int = 50) -> list[Call]:
        stmt = (
            select(Call)
            .join(CallParticipant, CallParticipant.call_id == Call.id)
            .where(CallParticipant.user_id == user_id)
            .order_by(Call.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).unique().scalars().all())