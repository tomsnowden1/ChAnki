"""AnkiConnect service for adding cards to Anki"""
import requests
from typing import Dict, List, Optional


class AnkiService:
    """Service for interacting with AnkiConnect API"""
    
    def __init__(self, url: str = "http://localhost:8765"):
        self.url = url
        self.version = 6
    
    def _invoke(self, action: str, params: Optional[Dict] = None) -> Dict:
        """
        Invoke an AnkiConnect API action
        
        Args:
            action: The API action to invoke
            params: Parameters for the action
        
        Returns:
            Response from AnkiConnect
        
        Raises:
            Exception: If AnkiConnect returns an error or is not reachable
        """
        payload = {
            'action': action,
            'version': self.version
        }
        
        if params:
            payload['params'] = params
        
        try:
            response = requests.post(self.url, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json()
            
            if 'error' in result and result['error']:
                raise Exception(f"AnkiConnect error: {result['error']}")
            
            return result.get('result')
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to connect to AnkiConnect: {str(e)}")
    
    def check_connection(self) -> bool:
        """Check if AnkiConnect is running and accessible"""
        try:
            self._invoke('version')
            return True
        except Exception:
            return False
    
    def check_duplicate(self, hanzi: str, deck_name: str) -> bool:
        """
        Check if a card with the given Hanzi already exists in the deck
        
        Args:
            hanzi: The Chinese character(s) to check
            deck_name: The deck name to check (e.g., 'Chinese::Vocabulary')
        
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Search for notes in the deck with matching Hanzi field
            query = f'"deck:{deck_name}" "Hanzi:{hanzi}"'
            note_ids = self._invoke('findNotes', {'query': query})
            
            return len(note_ids) > 0
        except Exception as e:
            print(f"Error checking duplicate: {e}")
            return False
    
    def add_note(self, hanzi: str, pinyin: str, definition: str, 
                 cloze_sentence: str, cloze_translation: str,
                 deck_name: str, note_type: str = "Chinese-Cloze") -> bool:
        """
        Add a new note to Anki
        
        Args:
            hanzi: Chinese characters
            pinyin: Pinyin with tone marks
            definition: English definition
            cloze_sentence: Example sentence with cloze deletion
            cloze_translation: English translation of the sentence
            deck_name: Target deck name
            note_type: Note type to use
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, ensure the note type exists, or use Basic
            note_types = self._invoke('modelNames')
            
            if note_type not in note_types:
                # Fall back to a basic cloze type if custom doesn't exist
                if 'Cloze' in note_types:
                    note_type = 'Cloze'
                    # For standard Cloze, combine fields differently
                    fields = {
                        'Text': f"{cloze_sentence}<br><br>{pinyin}<br>{definition}",
                        'Extra': cloze_translation
                    }
                else:
                    # Last resort: use Basic
                    note_type = 'Basic'
                    fields = {
                        'Front': f"{hanzi}<br>{pinyin}",
                        'Back': f"{definition}<br><br>{cloze_sentence}<br>{cloze_translation}"
                    }
            else:
                # Use custom note type with specific fields
                fields = {
                    'Hanzi': hanzi,
                    'Pinyin': pinyin,
                    'Definition': definition,
                    'Cloze': cloze_sentence,
                    'Translation': cloze_translation
                }
            
            note = {
                'deckName': deck_name,
                'modelName': note_type,
                'fields': fields,
                'options': {
                    'allowDuplicate': False
                },
                'tags': ['chanki']
            }
            
            note_id = self._invoke('addNote', {'note': note})
            return note_id is not None
            
        except Exception as e:
            print(f"Error adding note: {e}")
            return False
    
    def get_deck_names(self) -> List[str]:
        """Get list of all deck names"""
        try:
            return self._invoke('deckNames')
        except Exception:
            return []
    
    def create_deck(self, deck_name: str) -> bool:
        """Create a new deck"""
        try:
            self._invoke('createDeck', {'deck': deck_name})
            return True
        except Exception:
            return False
