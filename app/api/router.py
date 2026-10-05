from fastapi import APIRouter

from app.api import (
    admin,
    auth,
    calls,
    blocks,
    chats,
    files,
    messages,
    reports,
    search,
    users,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(chats.router)
api_router.include_router(messages.router)
api_router.include_router(search.router)
api_router.include_router(files.router)
api_router.include_router(calls.router)
api_router.include_router(blocks.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)