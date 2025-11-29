from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/api/products", tags=["products"])

@router.get("", response_model=List[schemas.ProductOut])
def list_products(
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
):
    query = db.query(models.Product)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(models.Product.title.ilike(like))
    if min_price is not None:
        query = query.filter(models.Product.price_cents >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price_cents <= max_price)
    return query.order_by(models.Product.id.desc()).all()

@router.post("", response_model=schemas.ProductOut, status_code=201)
def create_product(product_in: schemas.ProductCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # In a next step, you can restrict to admin users
    product = models.Product(**product_in.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
