"""AI fallback cache — persists Gemini-defined words so each query costs one API call"""
from sqlalchemy import Column, Integer, String, DateTime
from app.models.settings import Base
from datetime import datetime


class AICache(Base):
    __tablename__ = "ai_cache"

    id = Column(Integer, primary_key=True)
    query_text = Column(String, nullable=False, unique=True, index=True)
    hanzi = Column(String, nullable=False)
    pinyin = Column(String, nullable=False)
    definition = Column(String, nullable=False)
    part_of_speech = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
