from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import (
    ProducerOrderLineRead,
    ProducerOrderListResponse,
    ProducerOrderRead,
    ProductListResponse,
    ProductRead,
    ProductUpdate,
    ProducerInsights,
)
from app.services import orders as orders_service
from app.services import products as products_service
from app.services import ml as ml_service

router = APIRouter(prefix="/producer", tags=["producer"])


@router.get("/products", response_model=ProductListResponse)
async def list_my_products(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListResponse:
    items, total = await products_service.list_products_for_producer(
        db,
        producer=current_producer,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[ProductRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
) -> ProductRead:
    product = await products_service.get_product_for_producer(
        db, producer=current_producer, product_id=product_id
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    updated = await products_service.update_product(db, product=product, payload=payload)
    return ProductRead.model_validate(updated)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
) -> None:
    product = await products_service.get_product_for_producer(
        db, producer=current_producer, product_id=product_id
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await products_service.delete_product(db, product=product)


@router.get("/orders", response_model=ProducerOrderListResponse)
async def list_my_orders(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProducerOrderListResponse:
    orders, total = await orders_service.list_orders_for_producer(
        db,
        producer=current_producer,
        limit=limit,
        offset=offset,
    )

    items: list[ProducerOrderRead] = []
    for order in orders:
        lines: list[ProducerOrderLineRead] = []
        for line in order.lines:
            if line.product is not None and line.product.producer_id != current_producer.id:
                continue
            if line.product is None and line.product_id is None:
                continue
            lines.append(
                ProducerOrderLineRead(
                    id=line.id,
                    order_id=order.id,
                    product_id=line.product_id,
                    product_title=line.product_title,
                    quantity=line.quantity,
                    unit_price_cents=line.unit_price_cents,
                    reference_price_cents=line.reference_price_cents,
                    subtotal_cents=line.subtotal_cents,
                    created_at=line.created_at,
                )
            )
        if not lines:
            continue
        subtotal = sum(l.subtotal_cents for l in lines)
        items.append(
            ProducerOrderRead(
                order_id=order.id,
                status=order.status,
                customer_id=order.user.id,
                customer_email=order.user.email,
                created_at=order.created_at,
                total_amount_cents=subtotal,
                lines=lines,
            )
        )

    return ProducerOrderListResponse(items=items, total=total, limit=limit, offset=offset)



@router.get("/insights", response_model=ProducerInsights)
async def producer_insights(
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
) -> ProducerInsights:
    data = await orders_service.compute_producer_insights(db, producer=current_producer)
    return ProducerInsights(**data)


@router.get("/recommendations/forecast")
async def forecast_recommendations(
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
):
    result = await ml_service.forecast_per_product(db, producer=current_producer)
    return {"items": result}


@router.get("/recommendations/segments")
async def customer_segments(
    db: AsyncSession = Depends(deps.get_db),
    current_producer=Depends(deps.get_current_producer),
    k: int = Query(default=3, ge=2, le=6),
):
    # For MVP, clusters are global; can be refined per producer later
    result = await ml_service.cluster_consumers(db, k=k)
    return result
