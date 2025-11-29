from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    """Accept an image upload and return a public URL (served from /static)."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file")

    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(file.content_type, ".bin")

    uploads_dir = Path("static") / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    import uuid

    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = uploads_dir / filename

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    dest.write_bytes(contents)

    # Front can prefix with API base
    return {"url": f"/static/uploads/{filename}"}

