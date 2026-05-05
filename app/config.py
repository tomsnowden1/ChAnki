"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings
from pydantic import Field


# Sentinel value for the unset SYNC_SECRET. Refused at startup in production.
DEFAULT_DEV_SYNC_SECRET = "development_secret_change_in_production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    database_url: str = Field(default="sqlite:///./chanki.db", env="DATABASE_URL")

    # OpenAI API
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")

    # AnkiConnect
    anki_connect_url: str = Field(default="http://localhost:8765", env="ANKI_CONNECT_URL")

    # Sync — shared secret between server and local sync agent
    sync_secret: str = Field(default=DEFAULT_DEV_SYNC_SECRET, env="SYNC_SECRET")

    # Deployment env. Use "production" on Render; default "development" locally.
    environment: str = Field(default="development", env="ENVIRONMENT")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
