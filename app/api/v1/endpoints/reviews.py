from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import ReviewCreate, ReviewListResponse, ReviewRead
from app.services import reviews as reviews_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    request: Request,
    payload: ReviewCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> ReviewRead:
    # Anti-spam léger par IP
    await deps.enforce_ip_rate_limit(request, prefix="reviews")
    try:
        review = await reviews_service.create_review(db, user=current_user, payload=payload)
    except reviews_service.ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ReviewRead.model_validate(review)


@router.get("/product/{product_id}", response_model=ReviewListResponse)
async def list_product_reviews(
    product_id: int,
    db: AsyncSession = Depends(deps.get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewListResponse:
    reviews, total = await reviews_service.list_product_reviews(
        db, product_id=product_id, limit=limit, offset=offset
    )
    return ReviewListResponse(
        items=[ReviewRead.model_validate(r) for r in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{review_id}", response_model=ReviewRead)
async def update_review(
    review_id: int,
    payload: ReviewCreate,  # reuse fields rating/comment/product_id (server checks author & product match)
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> ReviewRead:
    review = await reviews_service.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    try:
        updated = await reviews_service.update_review(db, review=review, user=current_user, payload=payload)
    except reviews_service.ReviewPermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReviewRead.model_validate(updated)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> None:
    review = await reviews_service.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    try:
        await reviews_service.delete_review(db, review=review, user=current_user)
    except reviews_service.ReviewPermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me", response_model=ReviewListResponse)
async def list_my_reviews(
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReviewListResponse:
    reviews, total = await reviews_service.list_reviews_for_user(
        db, user=current_user, limit=limit, offset=offset
    )
    return ReviewListResponse(
        items=[ReviewRead.model_validate(r) for r in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )
