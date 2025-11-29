from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import AdminUserCreate, AdminUserStatusUpdate, UserRead, UserRoleUpdate
from app.services import audit as audit_service
from app.services import users as users_service
from app.services.users import UserAlreadyExistsError

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
async def list_users(
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = await users_service.list_users(db, limit=limit, offset=offset)
    return {
        "items": [UserRead.model_validate(u) for u in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    payload: AdminUserCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> UserRead:
    try:
        user = await users_service.create_user(db, payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="admin.user_create",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"target": user.id, "role": user.role.value},
    )
    return UserRead.model_validate(user)


@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(
    request: Request,
    user_id: int,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> UserRead:
    user = await users_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    updated = await users_service.set_user_role(db, user=user, role=payload.role)
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="admin.user_role_update",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"target": user.id, "role": payload.role.value},
    )
    return UserRead.model_validate(updated)


@router.patch("/{user_id}/status", response_model=UserRead)
async def update_user_status(
    request: Request,
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> UserRead:
    user = await users_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = payload.is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="admin.user_status_update",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"target": user.id, "is_active": payload.is_active},
    )
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
):
    user = await users_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await users_service.delete_user(db, user)
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="admin.user_delete",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"target": user.id},
    )
    return {"ok": True}
