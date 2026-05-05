"""SQLAlchemy Settings model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class AppSettings(Base):
    """Application settings stored in database"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    anki_deck_name = Column(String, default="Chinese::Mining")
    anki_model_name = Column(String, default="ChAnki-Advanced")
    openai_api_key = Column(String, nullable=True)
    hsk_target_level = Column(Integer, default=3)
    tone_colors_enabled = Column(Boolean, default=True)
    generate_audio = Column(Boolean, default=True)
    strict_mode = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Sentinel returned to the frontend so it knows a key is set without seeing it
    KEY_SET_SENTINEL = "••••••••"

    def to_dict(self):
        return {
            "anki_deck_name": self.anki_deck_name,
            "anki_model_name": self.anki_model_name,
            "openai_api_key": self.KEY_SET_SENTINEL if self.openai_api_key else "",
            "hsk_target_level": self.hsk_target_level,
            "tone_colors_enabled": self.tone_colors_enabled,
            "generate_audio": self.generate_audio,
            "strict_mode": self.strict_mode,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
