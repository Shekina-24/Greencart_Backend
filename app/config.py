from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


# =====================================================
# ✅ Chargement .env.dev uniquement en LOCAL
# - En Railway/prod : on ne charge rien, on lit les variables Railway
# - En local : si .env.dev existe, on le charge sans écraser l'environnement
# =====================================================
def _load_local_env() -> None:
    env = os.getenv("ENV", "").lower()  # tu peux mettre ENV=local sur ton PC
    if env in {"local", "dev"}:
        try:
            from dotenv import load_dotenv
        except ImportError:
            return

        env_path = Path(__file__).parent.parent / ".env.dev"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)


_load_local_env()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        
        extra="ignore",
    )

    # -----------------
    # Core
    # -----------------
    project_name: str = Field(default="Greencart API", alias="PROJECT_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_str: str = Field(default="/api/v1", alias="API_V1_STR")

    # -----------------
    # Database (⚠️ PAS DE DEFAULT EN PROD)
    # -----------------
    database_url: str = Field(..., alias="DATABASE_URL")

    # -----------------
    # JWT (⚠️ OBLIGATOIRE EN PROD)
    # -----------------
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=4320, alias="REFRESH_TOKEN_EXPIRE_MINUTES")

    # -----------------
    # CORS
    # -----------------
    cors_origins_raw: str | List[str] | None = Field(default=None, alias="CORS_ORIGINS")

    # -----------------
    # Redis / Rate limiting
    # -----------------
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    rate_limit_per_minute: int = Field(default=120, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_rules_raw: str | Dict[str, Tuple[int, int]] | None = Field(
        default=None, alias="RATE_LIMIT_RULES"
    )

    # -----------------
    # Email (SMTP + templates) — ✅ 1 seule fois (plus de doublon)
    # -----------------
    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
    email_template_dir: str = Field(default="app/email_templates", alias="EMAIL_TEMPLATE_DIR")
    email_sender: str | None = Field(default=None, alias="EMAIL_SENDER")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    email_default_locale: str = Field(default="fr", alias="EMAIL_DEFAULT_LOCALE")

    # -----------------
    # Reports
    # -----------------
    reports_storage_dir: str = Field(default="generated_reports", alias="REPORTS_STORAGE_DIR")
    enable_monthly_reports: bool = Field(default=False, alias="ENABLE_MONTHLY_REPORTS")
    monthly_report_hour_utc: int = Field(default=6, alias="MONTHLY_REPORT_HOUR_UTC")

    # -----------------
    # Mailjet
    # -----------------
    mailjet_api_key: str | None = Field(default=None, alias="MAILJET_API_KEY")
    mailjet_api_secret: str | None = Field(default=None, alias="MAILJET_API_SECRET")
    mailjet_from_email: str | None = Field(default=None, alias="MAILJET_FROM_EMAIL")
    mailjet_from_name: str | None = Field(default=None, alias="MAILJET_FROM_NAME")

    # -----------------
    # Power BI
    # -----------------
    powerbi_embed_url: str | None = Field(default=None, alias="POWERBI_EMBED_URL")
    powerbi_static_token: str | None = Field(default=None, alias="POWERBI_STATIC_TOKEN")
    powerbi_token_ttl_seconds: int = Field(default=3600, alias="POWERBI_TOKEN_TTL_SECONDS")

    # =====================================================
    # Computed fields
    # =====================================================

    @computed_field(return_type=List[str])
    @property
    def cors_origins(self) -> List[str]:
        """Normalise CORS origins."""
        raw = self.cors_origins_raw
        if raw is None or raw == "":
            return []
        if isinstance(raw, str):
            return _split_csv(raw)
        return [str(item).strip() for item in raw if str(item).strip()]

    @computed_field(return_type=Dict[str, Tuple[int, int]])
    @property
    def rate_limit_rules(self) -> Dict[str, Tuple[int, int]]:
        raw = self.rate_limit_rules_raw
        if not raw:
            return {}

        if isinstance(raw, dict):
            return {
                str(k): (int(v[0]), int(v[1]))
                for k, v in raw.items()
                if isinstance(v, (list, tuple)) and len(v) == 2
            }

        rules: Dict[str, Tuple[int, int]] = {}
        for chunk in _split_csv(raw):
            namespace, _, rest = chunk.partition(":")
            limit, _, window = rest.partition("/")
            try:
                rules[namespace] = (int(limit), int(window))
            except ValueError:
                continue
        return rules


# ✅ Instance unique
settings = Settings()
