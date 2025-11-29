from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Tuple
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import settings
from ..schemas import RefreshTokenPayload, TokenPayload


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def _build_token_payload(
    subject: str,
    expires_delta: timedelta,
    scope: Literal["access", "refresh"],
    jti: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    token_jti = jti or uuid4().hex
    return {
        "sub": subject,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "scope": scope,
        "jti": token_jti,
    }


def _encode_token(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, *, jti: str | None = None) -> Tuple[str, TokenPayload]:
    payload_dict = _build_token_payload(
        subject,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        scope="access",
        jti=jti,
    )
    return _encode_token(payload_dict), TokenPayload(**payload_dict)


def create_refresh_token(subject: str, *, jti: str | None = None) -> Tuple[str, RefreshTokenPayload]:
    payload_dict = _build_token_payload(
        subject,
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
        scope="refresh",
        jti=jti,
    )
    return _encode_token(payload_dict), RefreshTokenPayload(**payload_dict)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def parse_token(token: str, scope: Literal["access", "refresh"]) -> TokenPayload | RefreshTokenPayload:
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise InvalidTokenError("Could not validate credentials") from exc

    if payload.get("scope") != scope:
        raise InvalidTokenError("Invalid token scope")

    model = RefreshTokenPayload if scope == "refresh" else TokenPayload
    return model(**payload)


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be validated."""
