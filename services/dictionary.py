"""Chinese dictionary service using CC-CEDICT"""
import re
from pypinyin import pinyin, Style
import jieba
from typing import List, Dict, Optional


class DictionaryService:
    """Service for Chinese word lookups using CC-CEDICT"""
    
    def __init__(self, cedict_path: str):
        self.cedict_path = cedict_path
        self.entries = []
        self._load_dictionary()
    
    def _load_dictionary(self):
        """Load and parse CC-CEDICT dictionary file"""
        try:
            with open(self.cedict_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line.startswith('#') or not line:
                        continue
                    
                    # Parse CEDICT format: 繁體 简体 [pin1 yin1] /definition1/definition2/
                    match = re.match(r'(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/', line)
                    if match:
                        traditional, simplified, pinyin_text, definitions = match.groups()
                        entry = {
                            'traditional': traditional,
                            'simplified': simplified,
                            'pinyin': pinyin_text,
                            'definitions': definitions.split('/')
                        }
                        self.entries.append(entry)
            
            print(f"Loaded {len(self.entries)} dictionary entries")
        except FileNotFoundError:
            print(f"Warning: Dictionary file not found at {self.cedict_path}")
            self.entries = []
    
    def search(self, query: str) -> List[Dict[str, any]]:
        """
        Search for Chinese words by English, Pinyin, or Hanzi
        
        Args:
            query: Search term (English word, Pinyin, or Chinese characters)
        
        Returns:
            List of matching dictionary entries
        """
        query = query.strip().lower()
        results = []
        
        # Check if query contains Chinese characters
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
        
        if has_chinese:
            # Search by Hanzi (simplified or traditional)
            results = self._search_by_hanzi(query)
        elif self._is_pinyin(query):
            # Search by Pinyin
            results = self._search_by_pinyin(query)
        else:
            # Search by English definition
            results = self._search_by_english(query)
        
        # Format results
        formatted_results = []
        for entry in results[:10]:  # Limit to top 10 results
            formatted_results.append({
                'hanzi': entry['simplified'],
                'traditional': entry['traditional'],
                'pinyin': entry['pinyin'],
                'definitions': entry['definitions']
            })
        
        return formatted_results
    
    def _search_by_hanzi(self, hanzi: str) -> List[Dict]:
        """Search by Chinese characters"""
        results = []
        for entry in self.entries:
            if hanzi in entry['simplified'] or hanzi in entry['traditional']:
                # Prioritize exact matches
                if entry['simplified'] == hanzi or entry['traditional'] == hanzi:
                    results.insert(0, entry)
                else:
                    results.append(entry)
        return results
    
    def _search_by_pinyin(self, query: str) -> List[Dict]:
        """Search by Pinyin (with or without tone numbers)"""
        # Normalize pinyin: remove spaces, convert to lowercase
        query_normalized = query.replace(' ', '').lower()
        
        results = []
        for entry in self.entries:
            entry_pinyin = entry['pinyin'].replace(' ', '').lower()
            # Remove tone numbers for flexible matching
            entry_pinyin_no_tones = re.sub(r'[0-9]', '', entry_pinyin)
            query_no_tones = re.sub(r'[0-9]', '', query_normalized)
            
            if query_normalized in entry_pinyin or query_no_tones in entry_pinyin_no_tones:
                results.append(entry)
        
        return results
    
    def _search_by_english(self, query: str) -> List[Dict]:
        """Search by English definition"""
        results = []
        for entry in self.entries:
            for definition in entry['definitions']:
                if query in definition.lower():
                    results.append(entry)
                    break
        return results
    
    def _is_pinyin(self, text: str) -> bool:
        """Check if text looks like Pinyin"""
        # Basic heuristic: contains only ASCII letters, numbers, and spaces
        # and has at least one vowel
        if not re.match(r'^[a-zA-Z0-9\s]+$', text):
            return False
        
        # Must have vowels
        if not re.search(r'[aeiouü]', text.lower()):
            return False
        
        # If it's too long or has too many words, likely English
        words = text.split()
        if len(words) > 4 or len(text) > 30:
            return False
        
        # Check for common pinyin patterns
        # Common pinyin finals: an, en, in, un, ang, eng, ing, ong, ao, ou, ai, ei
        pinyin_patterns = r'(zh|ch|sh|[bpmfdtnlgkhjqxzcsryw])?[aeiouü]+(ng|n|r|o)?[1-5]?'
        has_pinyin_pattern = bool(re.search(pinyin_patterns, text.lower()))
        
        # If text has numbers (tone marks), it's definitely pinyin
        if re.search(r'\d', text):
            return True
        
        # Otherwise, prefer English search unless it strongly looks like pinyin
        # (single short word, or multiple short words with pinyin patterns)
        if len(words) == 1 and len(text) <= 8 and has_pinyin_pattern:
            # Could be pinyin, but let's be conservative
            # Common English words are unlikely to be pinyin
            common_english = ['hello', 'love', 'good', 'bad', 'yes', 'no', 'the', 'and', 'for']
            if text.lower() in common_english:
                return False
            return True
        
        return False

    
    def get_pinyin(self, hanzi: str) -> str:
        """Convert Hanzi to Pinyin with tone marks"""
        return ' '.join([''.join(item) for item in pinyin(hanzi, style=Style.TONE)])
