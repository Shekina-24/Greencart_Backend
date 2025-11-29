from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

from app.config import settings


class TemplateNotFoundError(Exception):
    """Raised when a requested template cannot be located."""


@lru_cache(maxsize=16)
def _resolve_template_directory() -> Path:
    # Default directory: app/templates/email
    base_dir = settings.email_template_dir
    if base_dir:
        path = Path(base_dir)
    else:
        path = Path(__file__).resolve().parent.parent / "templates" / "email"
    return path


def _candidate_names(name: str, locale: str) -> list[Path]:
    directory = _resolve_template_directory()
    normalized_locale = locale.lower()
    return [
        directory / f"{name}_{normalized_locale}.txt",
        directory / f"{name}.txt",
    ]


def render_template(name: str, *, locale: str, context: Dict[str, Any]) -> str:
    for candidate in _candidate_names(name, locale):
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            return content.format(**context)
    raise TemplateNotFoundError(f"Template '{name}' not found for locale '{locale}'")


def render_json_payload(template_name: str, *, locale: str, context: Dict[str, Any]) -> dict[str, Any]:
    rendered = render_template(template_name, locale=locale, context=context)
    try:
        return json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Template {template_name} does not contain valid JSON") from exc


def render_email_content(
    name: str,
    *,
    locale: str,
    context: Dict[str, Any],
) -> Tuple[str, str]:
    rendered = render_template(name, locale=locale, context=context)
    if rendered.startswith("Subject:"):
        _, _, remainder = rendered.partition("\n")
        subject_line = rendered.split("\n", 1)[0]
        subject = subject_line.split("Subject:", 1)[1].strip()
        body = remainder.lstrip("\n")
        return subject, body
    raise ValueError(f"Template {name} missing subject header")
