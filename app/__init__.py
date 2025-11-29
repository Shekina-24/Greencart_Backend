"""Expose FastAPI app instance for ASGI servers."""

from .main import app  # noqa: F401

__all__ = ("app",)
