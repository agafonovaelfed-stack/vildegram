from enum import StrEnum


class ChatRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class BadgeKind(StrEnum):
    VERIFIED = "verified"
    SCAM = "scam"
    FAKE = "fake"
    V = "v"


ROLE_LEVEL: dict[ChatRole, int] = {
    ChatRole.OWNER: 100,
    ChatRole.ADMIN: 50,
    ChatRole.MEMBER: 10,
}


def role_at_least(role: ChatRole, minimum: ChatRole) -> bool:
    return ROLE_LEVEL.get(role, 0) >= ROLE_LEVEL.get(minimum, 0)


def can_manage_members(role: ChatRole) -> bool:
    return role_at_least(role, ChatRole.ADMIN)


def can_delete_chat(role: ChatRole) -> bool:
    return role == ChatRole.OWNER


def can_pin_messages(role: ChatRole) -> bool:
    return role_at_least(role, ChatRole.ADMIN)


def can_issue_badge(issuer_badges: list[BadgeKind], kind: BadgeKind) -> bool:
    """Правило: метку 'v' может выдать только владелец VildeGram.

    Остальные метки — любой, у кого есть метка 'v'.
    """
    if BadgeKind.V not in issuer_badges:
        return False
    return True