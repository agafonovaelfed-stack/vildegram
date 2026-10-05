import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def _build_message(to_email: str, code: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Код подтверждения VildeGram"
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    msg.set_content(
        f"""Здравствуйте!

Ваш код подтверждения VildeGram:

{code}

Код действует ограниченное время.

Если вы не запрашивали этот код, просто проигнорируйте это письмо.

VildeGram
"""
    )
    return msg


def _smtp_send_once(msg: EmailMessage) -> None:
    host = (settings.SMTP_HOST or "").strip()
    port = int(settings.SMTP_PORT or 0)
    user = (settings.SMTP_USER or "").strip()
    password = settings.SMTP_PASSWORD or ""

    if not host or not port or not user or not password:
        raise RuntimeError(
            "SMTP не настроен: проверьте SMTP_HOST, SMTP_PORT, SMTP_USER и SMTP_PASSWORD в backend/.env"
        )

    context = ssl.create_default_context()
    use_ssl = port == 465 or not settings.SMTP_TLS

    if use_ssl:
        with smtplib.SMTP_SSL(
            host,
            port,
            context=context,
            timeout=20,
        ) as server:
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)


def _send_email(to_email: str, code: str) -> None:
    msg = _build_message(to_email, code)

    # Создаём новое SMTP-соединение для каждой попытки. Это важно при
    # временном разрыве соединения Gmail до AUTH/LOGIN.
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            _smtp_send_once(msg)
            return
        except smtplib.SMTPServerDisconnected as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise RuntimeError(
                "Gmail SMTP закрыл соединение до авторизации. "
                "Проверьте порт 465, App Password и настройки SMTP в backend/.env."
            ) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "Gmail отклонил SMTP-авторизацию. Проверьте SMTP_USER и App Password."
            ) from exc
        except smtplib.SMTPException as exc:
            raise RuntimeError(f"SMTP ошибка: {exc}") from exc

    if last_error:
        raise last_error


async def send_login_code(to_email: str, code: str) -> None:
    await asyncio.to_thread(_send_email, to_email, code)
