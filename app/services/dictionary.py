"""Dictionary search service using SQLAlchemy"""
from sqlalchemy.orm import Session
from app.models.dictionary import DictionaryEntry
from typing import List
import re


class DictionaryService:
    """Service for searching the CC-CEDICT dictionary"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def search(self, query: str, limit: int = 20) -> List[DictionaryEntry]:
        """
        Search for Chinese words by English, Pinyin, or Hanzi
        
        Args:
            query: Search term
            limit: Maximum number of results
        
        Returns:
            List of matching dictionary entries
        """
        query = query.strip()
        
        if not query:
            return []
        
        # Check if query contains Chinese characters
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
        
        if has_chinese:
            return self._search_by_hanzi(query, limit)
        
        # For non-Chinese queries: try English first, then Pinyin
        # This ensures "dog", "cat", etc. match definitions before pinyin
        english_results = self._search_by_english(query, limit)
        if english_results:
            return english_results
        
        # No English results - try as Pinyin
        if self._is_pinyin(query):
            pinyin_results = self._search_by_pinyin(query, limit)
            if pinyin_results:
                return pinyin_results
        
        return []
    
    def _search_by_hanzi(self, hanzi: str, limit: int) -> List[DictionaryEntry]:
        """Search by Chinese characters"""
        # Exact match first
        exact = self.db.query(DictionaryEntry).filter(
            (DictionaryEntry.simplified == hanzi) | 
            (DictionaryEntry.traditional == hanzi)
        ).all()
        
        if exact:
            return exact[:limit]
        
        # Partial match
        results = self.db.query(DictionaryEntry).filter(
            (DictionaryEntry.simplified.contains(hanzi)) |
            (DictionaryEntry.traditional.contains(hanzi))
        ).limit(limit).all()
        
        return results
    
    def _search_by_pinyin(self, query: str, limit: int) -> List[DictionaryEntry]:
        """Search by Pinyin"""
        # Normalize: remove spaces, convert to lowercase
        query_normalized = query.replace(' ', '').lower()
        
        # Search with tone numbers
        results = self.db.query(DictionaryEntry).filter(
            DictionaryEntry.pinyin.ilike(f'%{query}%')
        ).limit(limit).all()
        
        return results
    
    def _search_by_english(self, query: str, limit: int) -> List[DictionaryEntry]:
        """Search by English definition"""
        query_lower = query.lower()
        
        # Search in definitions (stored as JSON string)
        results = self.db.query(DictionaryEntry).filter(
            DictionaryEntry.definitions.ilike(f'%{query_lower}%')
        ).limit(limit).all()
        
        return results
    
    def _is_pinyin(self, text: str) -> bool:
        """Check if text looks like Pinyin"""
        # Must be ASCII with vowels
        if not re.match(r'^[a-zA-Z0-9\s]+$', text):
            return False
        
        if not re.search(r'[aeiouü]', text.lower()):
            return False
        
        # If has tone numbers, definitely pinyin
        if re.search(r'\d', text):
            return True
        
        # Check length and common English words
        words = text.split()
        if len(words) > 4 or len(text) > 30:
            return False
        
        common_english = ['hello', 'love', 'good', 'bad', 'yes', 'no', 'the', 'and', 'for', 'to', 'of']
        if text.lower() in common_english:
            return False
        
        return True
    
    def get_by_hanzi(self, hanzi: str) -> List[DictionaryEntry]:
        """Get exact match by hanzi"""
        return self.db.query(DictionaryEntry).filter(
            (DictionaryEntry.simplified == hanzi) |
            (DictionaryEntry.traditional == hanzi)
        ).all()
    
    def search_with_ai_fallback(self, query: str, gemini_service, limit: int = 20):
        """
        Search with AI fallback - if 0 results, query Gemini API
        
        Args:
            query: Search term
            gemini_service: GeminiService instance for AI fallback
            limit: Maximum number of results
        
        Returns:
            Tuple of (results, is_ai_generated)
        """
        from app.models.dictionary import DictionaryEntry
        
        # First try standard search
        results = self.search(query, limit)
        
        if len(results) > 0:
            return results, False
        
        # No results - try AI fallback
        if not gemini_service or not gemini_service.model:
            return [], False
        
        try:
            # Query Gemini to define the term
            ai_result = gemini_service.define_word(query)
            
            if ai_result:
                # Create temporary entry (not saved to DB)
                temp_entry = DictionaryEntry(
                    traditional=ai_result.get('hanzi', ''),
                    simplified=ai_result.get('hanzi', ''),
                    pinyin=ai_result.get('pinyin', ''),
                    definitions=ai_result.get('definition', ''),
                    hsk_level=None,
                    classifier=None,
                    part_of_speech=ai_result.get('part_of_speech', None)
                )
                return [temp_entry], True
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.error(f"AI fallback failed: {e}")
        
        return [], False
