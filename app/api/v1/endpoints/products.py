from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import ProductCreate, ProductListResponse, ProductRead
from app.services import products as products_service

router = APIRouter(prefix="/products", tags=["catalog"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    *,
    db: AsyncSession = Depends(deps.get_db),
    q: Optional[str] = Query(default=None, description="Search term"),
    category: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    dlc_lte_days: Optional[int] = Query(default=None, ge=0, description="DLC within X days"),
    price_min: Optional[int] = Query(default=None, ge=0),
    price_max: Optional[int] = Query(default=None, ge=0),
    sort: str = Query(default="newest", description="Sort key"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListResponse:
    items, total = await products_service.list_products(
        db,
        limit=limit,
        offset=offset,
        q=q,
        category=category,
        region=region,
        dlc_within_days=dlc_lte_days,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
    )
    return ProductListResponse(
        items=[ProductRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: AsyncSession = Depends(deps.get_db)) -> ProductRead:
    product = await products_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductRead.model_validate(product)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    *,
    payload: ProductCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
) -> ProductRead:
    try:
        product = await products_service.create_product(
            db,
            producer=current_producer,
            product_in=payload,
        )
    except products_service.ProductPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ProductRead.model_validate(product)
