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
    definitions = Column(Text, nullable=False, index=True)  # JSON array stored as text
    hsk_level = Column(Integer, nullable=True, index=True)
    classifier = Column(String, nullable=True)  # Measure word (e.g., 个, 只)
    part_of_speech = Column(String, nullable=True)  # noun, verb, adjective, etc.

    
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
        return DictionaryEntry(
            traditional=traditional,
            simplified=simplified,
            pinyin=pinyin,
            definitions=json.dumps(definitions_list),
            hsk_level=None,
            classifier=None,
            part_of_speech=None
        )
