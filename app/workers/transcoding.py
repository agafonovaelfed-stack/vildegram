import uuid

from app.workers.celery_app import celery_app


@celery_app.task(name="transcoding.video")
def transcode_video(source_key: str, target_preset: str = "720p") -> dict:
    """Транскодинг видео в H.264/AAC с разными разрешениями.

    Потребует ffmpeg. Пока — заглушка.
    """
    return {
        "source_key": source_key,
        "preset": target_preset,
        "output_key": f"transcoded/{uuid.uuid4().hex}.mp4",
        "note": "ffmpeg not wired yet",
    }


@celery_app.task(name="transcoding.audio_waveform")
def extract_waveform(source_key: str) -> dict:
    """Извлечение волновой дорожки для голосовых сообщений.

    Возвращает JSON-массив амплитуд, который потом сохраняется в attachment.waveform.
    """
    # Пример: 40 пиков по 0..100
    peaks = [0] * 40
    return {
        "source_key": source_key,
        "peaks": peaks,
        "note": "waveform not implemented yet",
    }