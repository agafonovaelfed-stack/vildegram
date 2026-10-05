import io
from pathlib import Path

import socketio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.system import ensure_system_on_startup
from app.sockets.namespace import sio  # noqa: F401 — регистрация всех @sio.event

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup_system_bootstrap() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await ensure_system_on_startup(db)
    except Exception as e:
        print("[startup] system bootstrap failed:", e)


app.include_router(api_router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Local media fallback used when S3/MinIO is not configured.
local_uploads = Path.home() / "vildegram-data" / "uploads"
local_uploads.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=local_uploads), name="uploads")


@app.get("/")
async def root() -> dict:
    return {"app": settings.APP_NAME, "status": "ok"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/favicon.ico")
async def favicon() -> Response:
    size = 64
    img = Image.new("RGBA", (size, size), (5, 6, 10, 255))
    draw = ImageDraw.Draw(img)

    cx = cy = size // 2
    for r in range(cx, 0, -1):
        t = r / cx
        color = (
            int(46 + (0 - 46) * t),
            int(107 + (229 - 107) * t),
            255,
            255,
        )
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    draw.polygon(
        [(18, 16), (26, 16), (32, 44), (38, 16), (46, 16), (34, 50), (30, 50)],
        fill=(255, 255, 255, 255),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# Обёртка ASGI: сначала Socket.IO, потом FastAPI
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)