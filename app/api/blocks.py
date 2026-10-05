import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.block import Block
from app.models.user import User

router = APIRouter(prefix="/blocks", tags=["blocks"])

@router.get("")
async def list_blocks(current: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Block.blocked_id).where(Block.blocker_id == current.id))).scalars().all()
    return {"user_ids": [str(x) for x in rows]}

@router.post("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def block_user(user_id: uuid.UUID, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if user_id == current.id: raise HTTPException(400, "Cannot block yourself")
    exists = (await db.execute(select(Block.id).where(Block.blocker_id == current.id, Block.blocked_id == user_id))).scalar_one_or_none()
    if not exists:
        db.add(Block(blocker_id=current.id, blocked_id=user_id)); await db.commit()

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(user_id: uuid.UUID, current: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await db.execute(delete(Block).where(Block.blocker_id == current.id, Block.blocked_id == user_id)); await db.commit()
