from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models import ReviewStatus
from app.schemas import ReviewListResponse, ReviewModerationRequest, ReviewRead
from app.services import reviews as reviews_service

router = APIRouter(prefix="/admin/reviews", tags=["admin-reviews"])


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    status_filter: ReviewStatus = Query(default=ReviewStatus.PENDING),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewListResponse:
    reviews, total = await reviews_service.list_reviews_for_moderation(
        db, status=status_filter, limit=limit, offset=offset
    )
    return ReviewListResponse(
        items=[ReviewRead.model_validate(r) for r in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{review_id}/moderate", response_model=ReviewRead)
async def moderate_review(
    review_id: int,
    payload: ReviewModerationRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> ReviewRead:
    review = await reviews_service.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    moderated = await reviews_service.moderate_review(db, review=review, payload=payload)
    return ReviewRead.model_validate(moderated)
