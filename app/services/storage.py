import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


from app.core.config import settings


class StorageError(Exception):
    pass


class StorageService:
    """Хранилище файлов: S3 (MinIO/S3) или локальный диск.

    Если S3_ENDPOINT пустой — используется локальная папка uploads/.
    """

    LOCAL_ROOT = Path.home() / "vildegram-data" / "uploads"

    def __init__(self) -> None:
        self._client = None
        self._local = not bool(settings.S3_ENDPOINT)

    # ---------- S3-режим ----------

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.client import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def public_url(self, key: str) -> str:
        if self._local:
            return f"/static/uploads/{key}"
        base = settings.S3_PUBLIC_URL or f"{settings.S3_ENDPOINT}/{settings.S3_BUCKET}"
        return f"{base.rstrip('/')}/{key.lstrip('/')}"

    def build_key(self, *, prefix: str, owner_id: uuid.UUID, ext: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{prefix}/{owner_id}/{ts}-{uuid.uuid4().hex}.{ext.lstrip('.')}"

    async def ensure_bucket(self) -> None:
        if self._local:
            self.LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
            return
        try:
            self.client.head_bucket(Bucket=settings.S3_BUCKET)
        except Exception:
            self.client.create_bucket(Bucket=settings.S3_BUCKET)

    def generate_presigned_put(self, *, key: str, content_type: str | None = None, expires_in: int = 3600) -> str:
        if self._local:
            # локально — «presigned URL» это просто наш endpoint
            return f"/api/files/local-upload/{key}"
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key, "ContentType": content_type or "application/octet-stream"},
            ExpiresIn=expires_in,
        )

    def generate_presigned_get(self, *, key: str, expires_in: int = 3600) -> str:
        if self._local:
            return self.public_url(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str) -> None:
        if self._local:
            p = self._safe_local_path(key)
            if p.exists():
                p.unlink()
            return
        self.client.delete_object(Bucket=settings.S3_BUCKET, Key=key)

    # ---------- Локальный режим ----------

    def _safe_local_path(self, key: str) -> Path:
        raw = (key or "").replace("\\", "/").lstrip("/")
        path = (self.LOCAL_ROOT / raw).resolve()
        root = self.LOCAL_ROOT.resolve()
        if path != root and root not in path.parents:
            raise StorageError("Invalid storage key")
        return path

    def save_local(self, key: str, data: bytes) -> str:
        path = self._safe_local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.public_url(key)