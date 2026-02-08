from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.services.email import send_email, EmailNotConfiguredError, EmailSendError


router = APIRouter(prefix="/email", tags=["Email"])


class EmailTestIn(BaseModel):
    to_email: EmailStr


@router.post("/test")
async def test_email(payload: EmailTestIn):
    if not settings.email_enabled:
        raise HTTPException(status_code=400, detail="EMAIL_ENABLED=false (email désactivé)")

    try:
        await send_email(
            to=payload.to_email,
            subject="Test email — Greencart",
            body="Si tu lis ce message, l'envoi Mailjet fonctionne depuis l'API.",
            subtype="plain",
        )
        return {"sent": True}
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except EmailSendError as e:
        raise HTTPException(status_code=502, detail=str(e))
