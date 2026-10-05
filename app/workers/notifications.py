import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(name="notifications.send_push")
def send_push(user_id: str, title: str, body: str, data: dict | None = None) -> dict:
    """Отправка web-push уведомления.

    Пока — заглушка. Когда подключим pywebpush и VAPID-ключи,
    здесь будет реальная отправка на endpoint'ы, сохранённые в БД.
    """
    return {
        "user_id": user_id,
        "title": title,
        "body": body,
        "data": data or {},
        "delivered": False,
        "note": "push not implemented yet",
    }


@celery_app.task(name="notifications.broadcast_chat")
def broadcast_chat(chat_id: str, event: str, payload: dict) -> dict:
    """Отправка события всем участникам чата через Socket.IO.

    Из Celery-воркера нельзя просто так вызвать sio.emit — воркер живёт
    в отдельном процессе. Правильный путь — публикация в Redis pub/sub,
    которую слушает Socket.IO-сервер, и уже он раздаёт событие клиентам.
    """
    from app.core.config import settings
    import redis
    import json

    r = redis.from_url(settings.REDIS_URL)
    message = {"room": f"chat:{chat_id}", "event": event, "payload": payload}
    r.publish("vildegram:sio:broadcast", json.dumps(message))
    return {"published": True, "message": message}