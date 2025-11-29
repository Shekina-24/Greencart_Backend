"""WSGI/ASGI entrypoint for Azure App Service (gunicorn expects `application:app`)."""

from app.main import app

__all__ = ("app",)
