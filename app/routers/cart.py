from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/api/cart", tags=["cart"])

@router.get("", response_model=List[schemas.CartItemOut])
def get_my_cart(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    items = db.query(models.CartItem).filter(models.CartItem.user_id == user.id).all()
    return items

@router.post("", response_model=schemas.CartItemOut, status_code=201)
def add_to_cart(payload: schemas.CartAddItem, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    if product.stock < payload.quantity:
        raise HTTPException(status_code=400, detail="Stock insuffisant")

    item = db.query(models.CartItem).filter(models.CartItem.user_id == user.id, models.CartItem.product_id == product.id).first()
    if item:
        item.quantity += payload.quantity
    else:
        item = models.CartItem(user_id=user.id, product_id=product.id, quantity=payload.quantity)
        db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}", status_code=204)
def remove_item(item_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    item = db.query(models.CartItem).filter(models.CartItem.id == item_id, models.CartItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item introuvable")
    db.delete(item)
    db.commit()
    return
