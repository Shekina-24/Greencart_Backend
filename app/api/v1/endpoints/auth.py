import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    parse_token,
)
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshRequest,
    Token,
    UserCreate,
    UserRead,
)
from app.services import audit as audit_service
from app.services import email as email_service
from app.services import tokens as tokens_service
from app.services import users as users_service
from app.services.email import EmailSendError

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    payload: UserCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> UserRead:
    await deps.enforce_ip_rate_limit(request, prefix="register")
    try:
        user = await users_service.create_user(db, payload)
    except users_service.UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_service.log_audit_event(
        db,
        user=user,
        action="auth.register",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    try:
        await email_service.send_welcome_email(
            to=user.email,
            first_name=user.first_name,
            locale=getattr(user, "locale", None),
        )
    except EmailSendError as exc:
        logger.warning("Welcome email failed for %s: %s", user.email, exc)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(deps.get_db),
) -> Token:
    await deps.enforce_ip_rate_limit(request, prefix="login")

    user = await users_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    await users_service.touch_last_login(db, user)

    access_token, _ = create_access_token(user.email)
    refresh_token, refresh_payload = create_refresh_token(user.email)
    await tokens_service.store_refresh_token(
        db,
        user=user,
        token=refresh_token,
        payload=refresh_payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    await audit_service.log_audit_event(
        db,
        user=user,
        action="auth.login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    payload: RefreshRequest,
    db: AsyncSession = Depends(deps.get_db),
) -> Token:
    await deps.enforce_ip_rate_limit(request, prefix="refresh")
    try:
        token_payload = parse_token(payload.refresh_token, scope="refresh")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await users_service.get_user_by_email(db, token_payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    try:
        stored_token = await tokens_service.validate_refresh_token(
            db,
            user=user,
            token=payload.refresh_token,
            payload=token_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token, _ = create_access_token(user.email)
    new_refresh_token, new_refresh_payload = create_refresh_token(user.email)
    await tokens_service.rotate_refresh_token(
        db,
        user=user,
        old_record=stored_token,
        new_token=new_refresh_token,
        new_payload=new_refresh_payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    await audit_service.log_audit_event(
        db,
        user=user,
        action="auth.refresh",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"old_jti": token_payload.jti, "new_jti": new_refresh_payload.jti},
    )
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(deps.get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
