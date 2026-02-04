"""Card Queue Model for Cloud-Sync Architecture"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.models.settings import Base


class CardQueue(Base):
    """Cards waiting to be synced to local Anki"""
    __tablename__ = "card_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Card data
    hanzi = Column(String, nullable=False)
    pinyin = Column(String, nullable=False)
    definition = Column(String, nullable=False)
    
    # Example sentence
    sentence_hanzi = Column(String, nullable=True)
    sentence_pinyin = Column(String, nullable=True)
    sentence_english = Column(String, nullable=True)
    
    # Optional audio URL (TTS generated)
    audio_url = Column(String, nullable=True)
    
    # HSK level and part of speech
    hsk_level = Column(Integer, nullable=True)
    part_of_speech = Column(String, nullable=True)
    
    # Sync status tracking
    status = Column(String, default="pending", nullable=False)  # pending | synced | failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    synced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error tracking
    error_message = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<CardQueue(id={self.id}, hanzi={self.hanzi}, status={self.status})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "hanzi": self.hanzi,
            "pinyin": self.pinyin,
            "definition": self.definition,
            "sentence_hanzi": self.sentence_hanzi,
            "sentence_pinyin": self.sentence_pinyin,
            "sentence_english": self.sentence_english,
            "audio_url": self.audio_url,
            "hsk_level": self.hsk_level,
            "part_of_speech": self.part_of_speech,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "error_message": self.error_message
        }
