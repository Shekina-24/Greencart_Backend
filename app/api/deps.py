from collections.abc import AsyncIterator
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core import rate_limit
from ..core.security import InvalidTokenError, parse_token
from ..database import AsyncSessionLocal
from ..models import User, UserRole
from ..services import users as users_service


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_str}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_str}/auth/login", auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def _fetch_user_from_token(db: AsyncSession, token: str) -> User:
    try:
        payload = parse_token(token, scope="access")
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await users_service.get_user_by_email(db, payload.sub)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")
    return user


async def _enforce_rate_limit(identifier: str, *, namespace: str) -> None:
    allowed = await rate_limit.check_rate_limit(identifier, namespace=namespace)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = await _fetch_user_from_token(db, token)
    await _enforce_rate_limit(f"user:{user.id}", namespace="user")
    request.state.user = user
    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    token = await optional_oauth2_scheme(request)
    if not token:
        return None
    try:
        return await _fetch_user_from_token(db, token)
    except HTTPException:
        return None


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def get_current_consumer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.CONSUMER, UserRole.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consumer access required")
    return current_user


async def get_current_producer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.PRODUCER, UserRole.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Producer access required")
    return current_user


def ip_rate_limit_identifier(request: Request, prefix: str = "ip") -> str:
    return f"{prefix}:{_client_ip(request)}"


async def enforce_ip_rate_limit(request: Request, prefix: str = "ip") -> None:
    await _enforce_rate_limit(ip_rate_limit_identifier(request, prefix=prefix), namespace=prefix)
