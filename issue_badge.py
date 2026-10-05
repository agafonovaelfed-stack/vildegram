#!/usr/bin/env python3
"""Выдача метки из терминала.

Пример:
  python3 issue_badge.py <USER_UUID> v
  python3 issue_badge.py <USER_UUID> scam "не проводить сделки"

Скрипт использует первого пользователя с меткой v как владельца, если
VILDEGRAM_OWNER_ID не задан. Для production лучше задать VILDEGRAM_OWNER_ID.
"""
import asyncio, sys, uuid
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.badge import Badge
from app.services.badges import BadgeService

async def main():
    if len(sys.argv) < 3 or sys.argv[2] not in {"v","verified","scam","fake"}:
        print("Использование: python3 issue_badge.py <USER_UUID> <v|verified|scam|fake> [reason]")
        raise SystemExit(2)
    target = uuid.UUID(sys.argv[1]); kind=sys.argv[2]; reason=" ".join(sys.argv[3:]) or None
    async with AsyncSessionLocal() as db:
        owner_id = None
        import os
        if os.getenv("VILDEGRAM_OWNER_ID"):
            owner_id=uuid.UUID(os.environ["VILDEGRAM_OWNER_ID"])
        if owner_id is None:
            owner_id=(await db.execute(select(Badge.user_id).join(User, User.id == Badge.user_id).where(Badge.kind=="v", User.is_bot.is_(False)).limit(1))).scalar_one_or_none()
        if owner_id is None:
            raise SystemExit("Не найден владелец с меткой v. Задайте VILDEGRAM_OWNER_ID.")
        badge=await BadgeService(db).issue(target_user_id=target,kind=kind,issued_by=owner_id,reason=reason)
        print(f"OK: @{(await db.get(User,target)).username} -> {badge.kind}")

if __name__ == "__main__": asyncio.run(main())
