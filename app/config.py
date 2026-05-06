"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


# Sentinel value for the unset SYNC_SECRET. Refused at startup in production.
DEFAULT_DEV_SYNC_SECRET = "development_secret_change_in_production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        # Ignore unknown env vars — prevents stale keys (e.g. GEMINI_API_KEY)
        # from crashing startup on pydantic v2.
        extra="ignore",
    )

    # Database
    database_url: str = Field(default="sqlite:///./chanki.db")

    # OpenAI API
    openai_api_key: str = Field(default="")

    # AnkiConnect
    anki_connect_url: str = Field(default="http://localhost:8765")

    # Sync — shared secret between server and local sync agent
    sync_secret: str = Field(default=DEFAULT_DEV_SYNC_SECRET)

    # Deployment env. Use "production" on Render; default "development" locally.
    environment: str = Field(default="development")


# Global settings instance
settings = Settings()
