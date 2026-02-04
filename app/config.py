"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    database_url: str = Field(default="sqlite:///./chanki.db", env="DATABASE_URL")
    
    # Gemini API
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    
    # AnkiConnect
    anki_connect_url: str = Field(default="http://localhost:8765", env="ANKI_CONNECT_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
