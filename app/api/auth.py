from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordIn,
    EmailCodeRequest,
    EmailCodeVerify,
    EmailCodeResponse,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
)
from app.services.auth import (
    AuthService,
    AuthError,
    EmailTaken,
    InvalidCredentials,
    UsernameTaken,
)
from app.services.users import UserService, WrongPassword

router = APIRouter(prefix="/auth", tags=["auth"])




@router.post("/email/request-code", response_model=EmailCodeResponse)
async def request_email_code(
    data: EmailCodeRequest,
) -> EmailCodeResponse:
    service = AuthService(None)  # request_email_code does not touch the database
    try:
        code = await service.request_email_code(str(data.email))
    except AuthError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    # In DEBUG without SMTP the code is printed server-side, never exposed in production.
    dev_code = code if settings.DEBUG and not settings.SMTP_HOST else None
    return EmailCodeResponse(dev_code=dev_code)


@router.post("/email/verify", response_model=TokenPair)
async def verify_email_code(
    data: EmailCodeVerify,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> TokenPair:
    service = AuthService(db)
    existing_before = (await db.execute(select(User).where(User.email == str(data.email).strip().lower()))).scalar_one_or_none()
    try:
        user, access, refresh = await service.verify_email_code(
            email=str(data.email),
            code=data.code,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        from app.services.system import SystemService
        system = SystemService(db)
        if existing_before is None:
            await system.notify_welcome(user.id, user.display_name)
        else:
            await system.notify_login(
                user.id,
                device=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
            )
        await system.notify_code(user.id, data.code, purpose="входа")
        await db.commit()
    except Exception as e:
        print("[system] email login notify failed:", e)

    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> TokenPair:
    service = AuthService(db)
    try:
        _user, access, refresh = await service.register(
            username=data.username,
            email=data.email,
            password=data.password,
            display_name=data.display_name,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except UsernameTaken:
        raise HTTPException(status_code=409, detail="Username already taken")
    except EmailTaken:
        raise HTTPException(status_code=409, detail="Email already taken")

    try:
        from app.services.system import SystemService
        system = SystemService(db)
        await system.notify_welcome(_user.id, _user.display_name)
        await db.commit()
    except Exception as e:
        print("[system] welcome failed:", e)

    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair)
async def login(
    data: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> TokenPair:
    service = AuthService(db)
    try:
        _user, access, refresh = await service.login(
            email=data.email,
            password=data.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        from app.services.system import SystemService
        system = SystemService(db)
        await system.notify_login(
            _user.id,
            device=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
    except Exception as e:
        print("[system] login notify failed:", e)

    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    data: RefreshIn,
    db: AsyncSession = Depends(get_session),
) -> TokenPair:
    service = AuthService(db)
    try:
        access, new_refresh = await service.refresh(data.refresh_token)
    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))

    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = AuthService(db)
    await service.logout(current.id)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    service = UserService(db)
    try:
        await service.change_password(
            current,
            old_password=data.old_password,
            new_password=data.new_password,
        )
    except WrongPassword as e:
        raise HTTPException(status_code=400, detail=str(e))