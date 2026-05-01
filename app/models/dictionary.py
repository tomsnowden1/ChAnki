"""SQLAlchemy Dictionary model for CC-CEDICT entries"""
from sqlalchemy import Column, Integer, String, Text, Index
from app.models.settings import Base
import json


class DictionaryEntry(Base):
    """CC-CEDICT dictionary entry"""
    __tablename__ = "dictionary"
    
    id = Column(Integer, primary_key=True, index=True)
    traditional = Column(String, nullable=False, index=True)
    simplified = Column(String, nullable=False, index=True)
    pinyin = Column(String, nullable=False, index=True)
    pinyin_plain = Column(String, nullable=True, index=True)  # lowercase, no tones/spaces e.g. "nihao"
    definitions = Column(Text, nullable=False)  # JSON array stored as text
    hsk_level = Column(Integer, nullable=True, index=True)
    classifier = Column(String, nullable=True)
    part_of_speech = Column(String, nullable=True)

    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "traditional": self.traditional,
            "simplified": self.simplified,
            "pinyin": self.pinyin,
            "definitions": json.loads(self.definitions) if self.definitions else [],
            "hsk_level": self.hsk_level,
            "classifier": self.classifier,
            "part_of_speech": self.part_of_speech
        }
    
    @staticmethod
    def from_cedict(traditional, simplified, pinyin, definitions_list):
        """Create entry from CEDICT data"""
        import re
        plain = re.sub(r'[\d\s]', '', pinyin.lower())
        return DictionaryEntry(
            traditional=traditional,
            simplified=simplified,
            pinyin=pinyin,
            pinyin_plain=plain,
            definitions=json.dumps(definitions_list),
        )
