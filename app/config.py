from __future__ import annotations

from typing import Dict, List, Tuple

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = Field(
        default="Greencart API",
        validation_alias=AliasChoices("PROJECT_NAME"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG"),
    )
    api_v1_str: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices("API_V1_STR"),
    )

    database_url: str = Field(
        default="mysql+aiomysql://root:GoPQyeTyXxIsDrUlksipYlHEidzGhNPb@shortline.proxy.rlwy.net:37012/railway",
        validation_alias=AliasChoices("DATABASE_URL"),
    )

    jwt_secret: str = Field(
        default="change_me",
        validation_alias=AliasChoices("JWT_SECRET"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "JWT_ALG"),
    )
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    refresh_token_expire_minutes: int = Field(
        default=4320,
        validation_alias=AliasChoices("REFRESH_TOKEN_EXPIRE_MINUTES"),
    )

    cors_origins_raw: str | List[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )

    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL"),
    )
    rate_limit_per_minute: int = Field(
        default=120,
        validation_alias=AliasChoices("RATE_LIMIT_PER_MINUTE"),
    )
    rate_limit_rules_raw: str | Dict[str, Tuple[int, int]] | None = Field(
        default=None,
        validation_alias=AliasChoices("RATE_LIMIT_RULES"),
    )

    email_sender: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMAIL_SENDER"),
    )
    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT"),
    )
    smtp_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME"),
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD"),
    )
    email_default_locale: str | None = Field(
        default="fr",
        validation_alias=AliasChoices("EMAIL_DEFAULT_LOCALE"),
    )
    email_template_dir: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMAIL_TEMPLATE_DIR"),
    )

    reports_storage_dir: str = Field(
        default="generated_reports",
        validation_alias=AliasChoices("REPORTS_STORAGE_DIR"),
    )

    stripe_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STRIPE_SECRET_KEY"),
    )
    stripe_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STRIPE_WEBHOOK_SECRET"),
    )

    powerbi_embed_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("POWERBI_EMBED_URL"),
    )
    powerbi_static_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("POWERBI_STATIC_TOKEN"),
    )
    powerbi_token_ttl_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("POWERBI_TOKEN_TTL_SECONDS"),
    )

    enable_monthly_reports: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_MONTHLY_REPORTS"),
    )
    monthly_report_hour_utc: int = Field(
        default=6,
        validation_alias=AliasChoices("MONTHLY_REPORT_HOUR_UTC"),
    )

    mailjet_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MAILJET_API_KEY"),
    )
    mailjet_api_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MAILJET_API_SECRET"),
    )
    mailjet_from_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MAILJET_FROM_EMAIL"),
    )
    mailjet_from_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MAILJET_FROM_NAME"),
    )


    @computed_field(return_type=List[str])
    @property
    def cors_origins(self) -> List[str]:
        """Return normalized CORS origins list from CSV or JSON env value."""
        raw = self.cors_origins_raw
        if raw is None or raw == "":
            return ["https://greencart-front-end.vercel.app",
                    "http://localhost:3000",
                    "http://127.0.0.1:5500",]
        if isinstance(raw, str):
            origins = _split_csv(raw)
            return origins or ["http://127.0.0.1:5500",
                                "http://localhost:3000",
                               "https://greencart-front-end.vercel.app",]
        return [str(item).strip() for item in raw if str(item).strip()]

    @computed_field(return_type=Dict[str, Tuple[int, int]])
    @property
    def rate_limit_rules(self) -> Dict[str, Tuple[int, int]]:
        raw = self.rate_limit_rules_raw
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            parsed: Dict[str, Tuple[int, int]] = {}
            for namespace, rule in raw.items():
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    try:
                        parsed[str(namespace)] = (int(rule[0]), int(rule[1]))
                    except (TypeError, ValueError):
                        continue
            return parsed
        if isinstance(raw, str):
            rules: Dict[str, Tuple[int, int]] = {}
            for chunk in _split_csv(raw):
                namespace, sep, remainder = chunk.partition(":")
                if not sep:
                    continue
                limit_part, sep2, window_part = remainder.partition("/")
                if not sep2:
                    continue
                try:
                    limit_value = int(limit_part.strip())
                    window_value = int(window_part.strip())
                except ValueError:
                    continue
                rules[namespace.strip()] = (limit_value, window_value)
            return rules
        return {}

    @property
    def JWT_SECRET(self) -> str:
        return self.jwt_secret

    @property
    def JWT_ALG(self) -> str:
        return self.jwt_algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    @property
    def REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.refresh_token_expire_minutes


settings = Settings()
