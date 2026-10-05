#!/usr/bin/env bash
set -e

BACK="/Users/user/vildegram/backend"
mkdir -p "$BACK/app/services"

# ============================================================
# 1. SystemService — официальный чат VildeGram
# ============================================================
python3 - <<'PYEOF'
path = "/Users/user/vildegram/backend/app/services/system.py"

content = r'''"""Официальный системный чат VildeGram.

Автоматически создаёт:
  - юзера @vildegram с меткой "v" (владелец)
  - системный чат (kind="direct", is_service=True) между юзером и 
VildeGram
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.badge import Badge
from app.models.chat import Chat, ChatMember
from app.models.message import Message
from app.models.user import User


SYSTEM_USERNAME = "vildegram"
SYSTEM_EMAIL = "system@vildegram.local"
SYSTEM_DISPLAY_NAME = "VildeGram"
SYSTEM_PASSWORD = "system-account-no-login-" + uuid.uuid4().hex


class SystemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_system_user(self) -> User:
        stmt = select(User).where(User.username == SYSTEM_USERNAME)
        user = (await self.db.execute(stmt)).scalar_one_or_none()
        if user is not None:
            return user

        user = User(
            username=SYSTEM_USERNAME,
            email=SYSTEM_EMAIL,
            display_name=SYSTEM_DISPLAY_NAME,
            bio="Официальный аккаунт VildeGram. Уведомления, вход в 
аккаунт, обновления.",
            password_hash=hash_password(SYSTEM_PASSWORD),
            is_active=True,
            is_bot=True,
        )
        self.db.add(user)
        await self.db.flush()

        self.db.add(Badge(
            user_id=user.id,
            kind="v",
            revocable=False,
            reason="System account",
        ))
        await self.db.flush()
        return user

    async def ensure_chat_for(self, user_id: uuid.UUID) -> Chat:
        system_user = await self.ensure_system_user()

        sub = (
            select(ChatMember.chat_id)
            .where(ChatMember.user_id.in_([user_id, system_user.id]))
            .group_by(ChatMember.chat_id)
        )
        candidate_ids = [row[0] for row in (await 
self.db.execute(sub)).all()]
        if candidate_ids:
            stmt = (
                select(Chat)
                .where(Chat.id.in_(candidate_ids))
                .where(Chat.kind == "direct")
                .where(Chat.is_service.is_(True))
                .limit(1)
            )
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                return existing

        chat = Chat(
            kind="direct",
            created_by=system_user.id,
            title=SYSTEM_DISPLAY_NAME,
            is_service=True,
        )
        self.db.add(chat)
        await self.db.flush()

        self.db.add_all([
            ChatMember(chat_id=chat.id, user_id=system_user.id, 
role="owner"),
            ChatMember(chat_id=chat.id, user_id=user_id, role="member"),
        ])
        await self.db.flush()
        return chat

    async def notify(
        self,
        user_id: uuid.UUID,
        text: str,
        *,
        kind: str = "system",
    ) -> Message:
        system_user = await self.ensure_system_user()
        chat = await self.ensure_chat_for(user_id)

        msg = Message(
            chat_id=chat.id,
            sender_id=system_user.id,
            text=text,
            kind=kind,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def notify_welcome(self, user_id: uuid.UUID, display_name: str) 
-> Message:
        text = (
            "Добро пожаловать в VildeGram, " + display_name + "!\n\n"
            "Здесь будут появляться важные уведомления:\n"
            "- об обновлениях приложения\n"
            "- о входе в аккаунт с новых устройств\n"
            "- коды подтверждения и безопасность\n\n"
            "Если у вас есть вопросы — просто напишите в этот чат."
        )
        return await self.notify(user_id, text, kind="system")

    async def notify_login(
        self,
        user_id: uuid.UUID,
        device: str | None,
        ip_address: str | None = None,
    ) -> Message:
        when = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        text = "Вход в аккаунт\n\n"
        text += "Время: " + when + "\n"
        if device:
            text += "Устройство: " + device + "\n"
        if ip_address:
            text += "IP: " + ip_address + "\n"
        text += "\nЕсли это были не вы — смените пароль немедленно."
        return await self.notify(user_id, text, kind="system")


async def ensure_system_on_startup(db: AsyncSession) -> None:
    service = SystemService(db)
    await service.ensure_system_user()
    await db.commit()
'''

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("system.py:", len(content), "bytes")
PYEOF

# ============================================================
# 2. auth.py — хуки регистрации и логина
# ============================================================
python3 - <<'PYEOF'
path = "/Users/user/vildegram/backend/app/api/auth.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

old_reg = '''    except EmailTaken:
        raise HTTPException(status_code=409, detail="Email already taken")

    return TokenPair(access_token=access, refresh_token=refresh)'''

new_reg = '''    except EmailTaken:
        raise HTTPException(status_code=409, detail="Email already taken")

    try:
        from app.services.system import SystemService
        system = SystemService(db)
        await system.notify_welcome(_user.id, _user.display_name)
        await db.commit()
    except Exception as e:
        print("[system] welcome failed:", e)

    return TokenPair(access_token=access, refresh_token=refresh)'''

if old_reg in src and "notify_welcome" not in src:
    src = src.replace(old_reg, new_reg)
    print("auth: register hook added")
else:
    print("auth: register hook already present or pattern not found")

old_login = '''    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))

    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)'''

new_login = '''    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        from app.services.system import SystemService
        system = SystemService(db)
        await system.notify_login(
            _user.id,
            device=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
    except Exception as e:
        print("[system] login notify failed:", e)

    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)'''

if old_login in src and "notify_login" not in src:
    src = src.replace(old_login, new_login)
    print("auth: login hook added")
else:
    print("auth: login hook already present or pattern not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
PYEOF

# ============================================================
# 3. main.py — startup hook
# ============================================================
python3 - <<'PYEOF'
path = "/Users/user/vildegram/backend/app/main.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

if "ensure_system_on_startup" not in src:
    old_import = "from app.core.logging import setup_logging"
    new_import = (
        "from app.core.logging import setup_logging\n"
        "from app.db.session import AsyncSessionLocal\n"
        "from app.services.system import ensure_system_on_startup"
    )
    src = src.replace(old_import, new_import)

    marker = "app.include_router(api_router)"
    insert = '''@app.on_event("startup")
async def _startup_system_bootstrap() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await ensure_system_on_startup(db)
    except Exception as e:
        print("[startup] system bootstrap failed:", e)


app.include_router(api_router)'''

    if marker in src:
        src = src.replace(marker, insert, 1)
        print("main.py: startup hook added")
    else:
        print("main.py: marker not found")
else:
    print("main.py: startup hook already present")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
PYEOF

# ============================================================
# 4. messages.py — запрет записи в системный чат
# ============================================================
python3 - <<'PYEOF'
path = "/Users/user/vildegram/backend/app/services/messages.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

old = '''        await self._assert_member(chat_id, sender_id)

        has_text = bool(text and text.strip())'''

new = '''        await self._assert_member(chat_id, sender_id)

        from app.repositories.chats import ChatRepository as _CR
        _chat = await _CR(self.db).get_by_id(chat_id)
        if _chat is not None and getattr(_chat, "is_service", False):
            raise NotAMember("Системный чат доступен только для чтения")

        has_text = bool(text and text.strip())'''

if old in src and "Системный чат доступен только для чтения" not in src:
    src = src.replace(old, new)
    print("messages: service chat write blocked")
else:
    print("messages: already patched or marker not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
PYEOF

# ============================================================
# Проверка
# ============================================================
echo ""
echo "=== Проверка импорта backend ==="
cd "$BACK"
source .venv/bin/activate
python -c "import app.main; print('backend imports OK')"
