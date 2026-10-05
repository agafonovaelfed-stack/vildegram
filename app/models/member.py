"""Утилитарные Pydantic-совместимые типы для ролей участников.

Реальные ORM-таблицы участников (ChatMember, GroupMember, ChannelSubscriber)
лежат в chat.py, group.py и channel.py рядом со своими родителями.
Здесь — только константы и хелперы, чтобы не плодить дубликаты.
"""

from enum import StrEnum


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    SUBSCRIBER = "subscriber"


ROLE_LEVEL: dict[str, int] = {
    MemberRole.OWNER: 100,
    MemberRole.ADMIN: 50,
    MemberRole.MEMBER: 10,
    MemberRole.SUBSCRIBER: 5,
}


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_LEVEL.get(role, 0) >= ROLE_LEVEL.get(minimum, 0)