from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..api.deps import get_current_user

router = APIRouter(prefix="/api/donations", tags=["donations"])

@router.get("", response_model=list[schemas.DonationOut])
def list_donations(db: Session = Depends(get_db)):
    return db.query(models.Donation).order_by(models.Donation.created_at.desc()).all()

@router.post("", response_model=schemas.DonationOut, status_code=201)
def create_donation(
    payload: schemas.DonationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    donation = models.Donation(**payload.model_dump(), producer_id=user.id)
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation

@router.post("/{donation_id}/reserve", response_model=schemas.DonationOut)
def reserve_donation(
    donation_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    donation = db.query(models.Donation).filter(models.Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(404, "Don introuvable")
    if donation.status != "available":
        raise HTTPException(400, "Ce don n'est plus disponible")
    donation.status = "reserved"
    donation.reserved_by_id = user.id
    db.commit()
    db.refresh(donation)
    return donation