import io
import uuid

from app.workers.celery_app import celery_app


@celery_app.task(name="thumbnails.image")
def make_image_thumbnail(
    source_key: str,
    *,
    max_size: int = 512,
    output_key: str | None = None,
) -> dict:
    """Генерация превью для изображения.

    Скачивает из S3, режет через Pillow, заливает обратно и возвращает ключ.
    Пока — заготовка, реальная реализация после подключения MinIO/S3.
    """
    return {
        "source_key": source_key,
        "output_key": output_key or f"thumbs/{uuid.uuid4().hex}.jpg",
        "max_size": max_size,
        "note": "not implemented yet",
    }


@celery_app.task(name="thumbnails.video")
def make_video_thumbnail(source_key: str) -> dict:
    """Превью для видео. Потребует ffmpeg на воркере."""
    return {
        "source_key": source_key,
        "output_key": f"thumbs/{uuid.uuid4().hex}.jpg",
        "note": "ffmpeg not wired yet",
    }