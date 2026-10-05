from app.sockets.namespace import sio


async def notify_user(user_id: str, event: str, payload: dict) -> None:
    """Универсальный хелпер: отправить событие конкретному юзеру во все его вкладки."""
    await sio.emit(event, payload, room=f"user:{user_id}")


async def notify_chat(chat_id: str, event: str, payload: dict) -> None:
    await sio.emit(event, payload, room=f"chat:{chat_id}")