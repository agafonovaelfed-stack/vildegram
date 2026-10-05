from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "vildegram",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,          # жёсткий лимит 10 минут
    task_soft_time_limit=540,     # мягкий лимит 9 минут
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Импорт задач, чтобы Celery их увидел при старте воркера
celery_app.autodiscover_tasks(
    [
        "app.workers.notifications",
        "app.workers.thumbnails",
        "app.workers.transcoding",
    ]
)