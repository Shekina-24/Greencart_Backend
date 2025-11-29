from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="API health check")
async def health() -> dict[str, str]:
    """Simple health endpoint for uptime checks."""
    return {"status": "ok"}
