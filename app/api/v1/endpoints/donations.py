from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app import models, schemas
from app.database import get_async_db
from app.api.deps import get_current_user

router = APIRouter(prefix="/donations", tags=["donations"])

@router.get("", response_model=list[schemas.DonationOut])
async def list_donations(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(
        select(models.Donation).order_by(models.Donation.created_at.desc())
    )
    return result.scalars().all()

@router.post("", response_model=schemas.DonationOut, status_code=201)
async def create_donation(
    payload: schemas.DonationCreate,
    db: AsyncSession = Depends(get_async_db),
    user: models.User = Depends(get_current_user)
):
    donation = models.Donation(**payload.model_dump(), producer_id=user.id)
    db.add(donation)
    await db.commit()
    await db.refresh(donation)
    return donation

@router.post("/{donation_id}/reserve", response_model=schemas.DonationOut)
async def reserve_donation(
    donation_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Donation).where(models.Donation.id == donation_id)
    )
    donation = result.scalar_one_or_none()
    if not donation:
        raise HTTPException(404, "Don introuvable")
    if donation.status != "available":
        raise HTTPException(400, "Ce don n'est plus disponible")
    donation.status = "reserved"
    donation.reserved_by_id = user.id
    await db.commit()
    await db.refresh(donation)
    return donation

@router.get("/mine", response_model=list[schemas.DonationOut])
async def my_donations(
    db: AsyncSession = Depends(get_async_db),
    user: models.User = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Donation).where(
            models.Donation.producer_id == user.id
        ).order_by(models.Donation.created_at.desc())
    )
    return result.scalars().all()