from __future__ import annotations

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload une image vers Cloudinary et retourne son URL publique."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    if settings.cloudinary_url:
        cloudinary.config(cloudinary_url=settings.cloudinary_url)

    result = cloudinary.uploader.upload(
        contents,
        folder="greencart/products",
        resource_type="image",
    )
    return {"url": result["secure_url"]}