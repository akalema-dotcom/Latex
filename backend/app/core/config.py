"""
app/core/config.py
==================
Application configuration loaded from environment variables.

USD is the system's default base currency, but every organization can
override its own currency, country, locale and timezone.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Union

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "AI Business Workforce"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_API_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./ai_business_workforce.db"

    # --- Security / JWT ---
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24

    # --- bcrypt ---
    BCRYPT_ROUNDS: int = 12

    # --- CORS ---
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:5173"
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- Rate limiting ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # --- Email ---
    EMAIL_PROVIDER: str = "console"  # console | smtp | noop
    EMAIL_FROM_ADDRESS: str = "noreply@example.com"
    EMAIL_FROM_NAME: str = "AI Business Workforce"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # --- Exchange rate provider ---
    EXCHANGE_RATE_PROVIDER: str = "mock"  # mock | manual | frankfurter | openexchangerates
    OPENEXCHANGERATES_APP_ID: Optional[str] = None
    EXCHANGE_RATE_CACHE_SECONDS: int = 3600  # 1 hour
    EXCHANGE_RATE_STALE_SECONDS: int = 86400  # 24h — after this, rates are "stale"

    # --- Frontend base URL (for verification / reset links) ---
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # ===== System-wide defaults (USD as base) =====
    SYSTEM_DEFAULT_CURRENCY_CODE: str = "USD"
    SYSTEM_DEFAULT_CURRENCY_SYMBOL: str = "$"
    SYSTEM_DEFAULT_LOCALE: str = "en-US"
    SYSTEM_DEFAULT_TIMEZONE: str = "UTC"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV.lower() == "testing"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
