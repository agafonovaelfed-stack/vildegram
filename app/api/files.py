import uuid

from fastapi import APIRouter, Depends, File as FastapiFile, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/files", tags=["files"])


class PresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=128)
    # avatars | attachments | recordings | thumbs
    scope: str = Field(default="attachments", pattern=r"^(avatars|attachments|recordings|thumbs)$")


class PresignOut(BaseModel):
    key: str
    upload_url: str
    public_url: str


@router.post("/presign", response_model=PresignOut)
async def presign_upload(
    data: PresignIn,
    current: User = Depends(get_current_user),
) -> PresignOut:
    """Выдаёт подписанный URL для прямой загрузки файла в S3/MinIO.

    Клиент загружает напрямую в S3 PUT-запросом по upload_url,
    потом отдаёт key серверу при отправке сообщения или сохранении аватара.
    """
    storage = StorageService()

    ext = data.filename.rsplit(".", 1)[-1] if "." in data.filename else "bin"
    key = storage.build_key(
        prefix=data.scope,
        owner_id=current.id,
        ext=ext,
    )

    try:
        upload_url = storage.generate_presigned_put(
            key=key, content_type=data.content_type
        )
    except StorageError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return PresignOut(
        key=key,
        upload_url=upload_url,
        public_url=storage.public_url(key),
    )


@router.get("/download/{key:path}")
async def download_url(
    key: str,
    _current: User = Depends(get_current_user),
) -> dict:
    storage = StorageService()
    try:
        url = storage.generate_presigned_get(key=key)
    except StorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"url": url}


# --- Локальное хранилище (когда S3_ENDPOINT пустой) ---


@router.put("/local-upload/{key:path}")
async def local_upload(
    key: str,
    file: UploadFile = FastapiFile(...),
    _current: User = Depends(get_current_user),
) -> dict:
    """Эндпоинт для локального хранилища (когда S3 не настроен)."""
    storage = StorageService()
    data = await file.read()
    storage.save_local(key, data)
    return {"ok": True, "key": key}


@router.get("/local-download/{key:path}")
async def local_download(key: str, _current: User = Depends(get_current_user)) -> FileResponse:
    storage = StorageService()
    try:
        path = storage._safe_local_path(key)
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)