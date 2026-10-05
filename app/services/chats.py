import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.permissions import ChatRole, can_delete_chat, can_manage_members
from app.models.chat import Chat, ChatMember
from app.models.group import Group, GroupMember
from app.models.channel import Channel, ChannelSubscriber
from app.repositories.chats import ChatRepository


class ChatError(Exception):
    pass


class ChatNotFound(ChatError):
    pass


class NotAMember(ChatError):
    pass


class NotAllowed(ChatError):
    pass


class PeerNotFound(ChatError):
    pass


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.chats = ChatRepository(db)

    async def get(self, chat_id: uuid.UUID) -> Chat:
        chat = await self.chats.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFound("Chat not found")
        return chat

    async def require_member(
        self, chat_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Chat, ChatMember]:
        chat = await self.get(chat_id)
        member = await self.chats.get_member(chat_id, user_id)
        if member is None:
            raise NotAMember("You are not a member of this chat")
        return chat, member

    async def list_for_user(
        self, user_id: uuid.UUID, *, include_archived: bool = False
    ) -> list[tuple[Chat, ChatMember]]:
        return await self.chats.list_for_user(
            user_id, include_archived=include_archived
        )

    async def create_direct(
        self, *, current_user_id: uuid.UUID, peer_id: uuid.UUID
    ) -> Chat:
        if peer_id == current_user_id:
            raise NotAllowed("Cannot create direct chat with yourself")

        existing = await self.chats.find_direct_between(current_user_id, peer_id)
        if existing is not None:
            return existing

        chat = await self.chats.create(kind="direct", created_by=current_user_id)
        await self.chats.add_member(chat.id, current_user_id, role="member")
        await self.chats.add_member(chat.id, peer_id, role="member")
        await self.db.commit()
        return chat

    async def create_group(
        self,
        *,
        owner_id: uuid.UUID,
        title: str,
        description: str | None = None,
        is_public: bool = False,
        username: str | None = None,
        member_ids: list[uuid.UUID] | None = None,
    ) -> Chat:
        chat = await self.chats.create(
            kind="group",
            created_by=owner_id,
            title=title,
            description=description,
            is_public=is_public,
            username=username,
        )
        await self.chats.add_member(chat.id, owner_id, role=ChatRole.OWNER.value)
        group = Group(chat_id=chat.id, owner_id=owner_id, title=title, description=description, is_public=is_public, username=username, member_count=1)
        self.db.add(group)
        await self.db.flush()
        self.db.add(GroupMember(group_id=group.id, user_id=owner_id, role="owner", can_send_messages=True, can_send_media=True, can_invite=True, can_pin=True, can_delete=True))

        for uid in (member_ids or []):
            if uid == owner_id:
                continue
            await self.chats.add_member(chat.id, uid, role="member")
            group = (await self.db.execute(select(Group).where(Group.chat_id == chat.id))).scalar_one_or_none()
            if group is not None:
                group.member_count += 1
                self.db.add(GroupMember(group_id=group.id, user_id=uid, role="member"))

        await self.db.commit()
        return chat

    async def create_channel(
        self,
        *,
        owner_id: uuid.UUID,
        title: str,
        description: str | None = None,
        is_public: bool = True,
        username: str | None = None,
    ) -> Chat:
        chat = await self.chats.create(
            kind="channel",
            created_by=owner_id,
            title=title,
            description=description,
            is_public=is_public,
            username=username,
        )
        await self.chats.add_member(chat.id, owner_id, role=ChatRole.OWNER.value)
        channel = Channel(chat_id=chat.id, owner_id=owner_id, title=title, description=description, is_public=is_public, username=username, subscriber_count=1)
        self.db.add(channel)
        await self.db.flush()
        self.db.add(ChannelSubscriber(channel_id=channel.id, user_id=owner_id, role="owner"))
        await self.db.commit()
        return chat

    async def update_chat(
        self,
        *,
        chat_id: uuid.UUID,
        actor_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        avatar_url: str | None = None,
        is_public: bool | None = None,
    ) -> Chat:
        chat, member = await self.require_member(chat_id, actor_id)
        if not can_manage_members(ChatRole(member.role)):
            raise NotAllowed("You cannot edit this chat")

        fields = {}
        if title is not None:
            fields["title"] = title
        if description is not None:
            fields["description"] = description
        if avatar_url is not None:
            fields["avatar_url"] = avatar_url
        if is_public is not None:
            fields["is_public"] = is_public

        updated = await self.chats.update_chat(chat, **fields)
        await self.db.commit()
        return updated

    async def add_members(
        self,
        *,
        chat_id: uuid.UUID,
        actor_id: uuid.UUID,
        user_ids: list[uuid.UUID],
    ) -> list[ChatMember]:
        chat, actor = await self.require_member(chat_id, actor_id)
        if not can_manage_members(ChatRole(actor.role)):
            raise NotAllowed("You cannot add members to this chat")

        added: list[ChatMember] = []
        for uid in user_ids:
            if await self.chats.is_member(chat_id, uid):
                continue
            member = await self.chats.add_member(chat_id, uid, role="member")
            added.append(member)

        await self.db.commit()
        return added

    async def remove_member(
        self,
        *,
        chat_id: uuid.UUID,
        actor_id: uuid.UUID,
        target_id: uuid.UUID,
    ) -> None:
        chat, actor = await self.require_member(chat_id, actor_id)

        # Себя может удалить любой
        if actor_id != target_id:
            if not can_manage_members(ChatRole(actor.role)):
                raise NotAllowed("You cannot remove members from this chat")
            target = await self.chats.get_member(chat_id, target_id)
            if target is not None and ChatRole(target.role) == ChatRole.OWNER:
                raise NotAllowed("Cannot remove the owner")

        await self.chats.remove_member(chat_id, target_id)
        await self.db.commit()

    async def update_member_settings(
        self,
        *,
        chat_id: uuid.UUID,
        actor_id: uuid.UUID,
        role: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
        is_muted: bool | None = None,
        target_id: uuid.UUID | None = None,
    ) -> ChatMember:
        chat, actor = await self.require_member(chat_id, actor_id)

        if target_id is None or target_id == actor_id:
            member = actor
            fields = {}
            if is_pinned is not None:
                fields["is_pinned"] = is_pinned
            if is_archived is not None:
                fields["is_archived"] = is_archived
            if is_muted is not None:
                fields["is_muted"] = is_muted
        else:
            if not can_manage_members(ChatRole(actor.role)):
                raise NotAllowed("You cannot change other members' roles")
            member = await self.chats.get_member(chat_id, target_id)
            if member is None:
                raise NotAMember("Target is not a member")
            fields = {}
            if role is not None:
                fields["role"] = role

        updated = await self.chats.update_member(member, **fields)
        await self.db.commit()
        return updated

    async def delete_chat(self, *, chat_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        chat, member = await self.require_member(chat_id, actor_id)
        if not can_delete_chat(ChatRole(member.role)):
            raise NotAllowed("Only the owner can delete this chat")
        await self.db.delete(chat)
        await self.db.commit()

    async def member_ids(self, chat_id: uuid.UUID) -> list[uuid.UUID]:
        return await self.chats.member_ids(chat_id)

    async def search_public(self, query: str) -> list[Chat]:
        return await self.chats.search_public(query)