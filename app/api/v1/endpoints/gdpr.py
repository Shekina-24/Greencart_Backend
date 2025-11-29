from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import UserRead
from app.services import audit as audit_service
from app.services import gdpr as gdpr_service

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


@router.get("/export", response_model=dict)
async def export_me(
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> dict:
    data = await gdpr_service.export_user_data(db, current_user)
    await audit_service.log_audit_event(
        db,
        user=current_user,
        action="gdpr.export",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return data


@router.delete("/erase", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> None:
    user_id = current_user.id
    await gdpr_service.erase_user_data(db, current_user)
    await audit_service.log_audit_event(
        db,
        user=None,
        action="gdpr.erase",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"user_id": user_id},
    )
