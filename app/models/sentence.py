"""SQLAlchemy models for Tatoeba/AI example sentences"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from app.models.settings import Base
from datetime import datetime


class Sentence(Base):
    """Example sentence (from Tatoeba or AI cache)"""
    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True, index=True)
    hanzi = Column(String, nullable=False)
    pinyin = Column(String, nullable=False)
    english = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    hsk_score = Column(Integer, nullable=True, index=True)
    char_length = Column(Integer, nullable=False, index=True)
    tatoeba_id = Column(Integer, nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SentenceWord(Base):
    """Inverted index: word → sentence_id (composite PK)"""
    __tablename__ = "sentence_words"

    word = Column(String, primary_key=True, index=True)
    sentence_id = Column(Integer, ForeignKey("sentences.id"), primary_key=True, index=True)
