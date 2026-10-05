import uuid

from jose import JWTError

from app.core.security import decode_token


class SocketAuthError(Exception):
    pass


def user_id_from_token(token: str) -> uuid.UUID:
    if not token:
        raise SocketAuthError("Missing token")
    try:
        payload = decode_token(token, expected_type="access")
        return uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as e:
        raise SocketAuthError(f"Invalid token: {e}") from e


def extract_token(auth: dict | None, environ: dict | None) -> str:
    """Достаёт токен из auth-payload или query string.

    Клиент может передать:
      - io(url, { auth: { token: '...' } })
      - io(url + '?token=...')
    """
    if auth and isinstance(auth, dict):
        t = auth.get("token")
        if t:
            return t

    if environ:
        query = environ.get("QUERY_STRING", "")
        for pair in query.split("&"):
            if pair.startswith("token="):
                return pair.split("=", 1)[1]
    return ""