from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import UserRead, UserUpdate
from app.services import audit as audit_service
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
async def update_me(
    request: Request,
    payload: UserUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> UserRead:
    try:
        user = await users_service.update_user(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await audit_service.log_audit_event(
        db,
        user=current_user,
        action="user.update",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return UserRead.model_validate(user)
