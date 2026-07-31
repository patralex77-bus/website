import secrets
from hmac import compare_digest
from flask import session


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf_token(token: str | None) -> bool:
    expected = session.get("_csrf_token")
    if not expected or not token:
        return False
    return compare_digest(expected, token)
