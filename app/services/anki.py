"""AnkiConnect service wrapper with comprehensive error handling"""
import requests
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class AnkiConnectError(Exception):
    """Custom exception for AnkiConnect errors"""
    pass


class AnkiService:
    """Service for interacting with AnkiConnect API"""
    
    def __init__(self, url: str = "http://localhost:8765"):
        self.url = url
        self.version = 6
    
    def _invoke(self, action: str, params: Optional[Dict] = None) -> Any:
        """
        Invoke an AnkiConnect API action
        
        Args:
            action: The API action to invoke
            params: Parameters for the action
        
        Returns:
            Response from AnkiConnect
        
        Raises:
            AnkiConnectError: If AnkiConnect returns an error or is not reachable
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
                raise AnkiConnectError(f"AnkiConnect error: {result['error']}")
            
            return result.get('result')
            
        except requests.exceptions.ConnectionError:
            raise AnkiConnectError("Cannot connect to AnkiConnect. Is Anki running?")
        except requests.exceptions.Timeout:
            raise AnkiConnectError("AnkiConnect request timed out")
        except requests.exceptions.RequestException as e:
            raise AnkiConnectError(f"Request failed: {str(e)}")
        except Exception as e:
            raise AnkiConnectError(f"Unexpected error: {str(e)}")
    
    def check_connection(self) -> bool:
        """Check if AnkiConnect is running and accessible"""
        try:
            self._invoke('version')
            return True
        except AnkiConnectError:
            return False

    def get_deck_names(self) -> List[str]:
        """Get list of all deck names"""
        try:
            return self._invoke('deckNames')
        except AnkiConnectError as e:
            logger.error(f"Failed to get deck names: {e}")
            return []
    
    def model_names(self) -> List[str]:
        """Get list of all note type names"""
        try:
            return self._invoke('modelNames')
        except AnkiConnectError as e:
            logger.error(f"Failed to get model names: {e}")
            return []
    
    def model_field_names(self, model_name: str) -> List[str]:
        """Get field names for a model"""
        try:
            return self._invoke('modelFieldNames', {'modelName': model_name})
        except AnkiConnectError as e:
            logger.error(f"Failed to get field names: {e}")
            return []
    
    def create_model(self, model_name: str, fields: List[str], card_templates: List[Dict]) -> bool:
        """
        Create a new note type (model)
        
        Args:
            model_name: Name of the note type
            fields: List of field names
            card_templates: List of card templates with 'Name', 'Front', 'Back'
        
        Returns:
            True if successful
        """
        try:
            params = {
                'modelName': model_name,
                'inOrderFields': fields,
                'css': self._get_card_css(),
                'isCloze': True,  # Enable cloze for {{c1::}} syntax
                'cardTemplates': card_templates
            }
            self._invoke('createModel', params)
            logger.info(f"Created note type: {model_name}")
            return True
        except AnkiConnectError as e:
            logger.error(f"Failed to create model: {e}")
            return False
    
    def ensure_model_exists(self, model_name: str) -> bool:
        """
        Ensure the ChAnki note type exists, creating it if necessary
        
        Returns:
            True if model exists or was created successfully
        """
        models = self.model_names()
        
        if model_name in models:
            logger.info(f"Note type '{model_name}' already exists")
            return True
        
        # Create the model with dual cards
        fields = [
            'Hanzi',
            'Pinyin',
            'English',
            'Audio',
            'Sentence_Hanzi',
            'Sentence_English',
            'Sentence_Audio',
            'Extra_Examples'  # NEW: Stores the 2 unused sentences
        ]

        
        # Dual card templates: Recall + Cloze
        card_templates = [
            {
                'Name': 'Recall',
                'Front': self._get_recall_card_front(),
                'Back': self._get_recall_card_back()
            },
            {
                'Name': 'Cloze',
                'Front': self._get_cloze_card_front(),
                'Back': self._get_cloze_card_back()
            }
        ]
        
        return self.create_model(model_name, fields, card_templates)
    
    def check_duplicate(self, hanzi: str, deck_name: str) -> bool:
        """
        Check if a card with the given Hanzi exists in the deck
        
        Args:
            hanzi: The Chinese character(s) to check
            deck_name: The deck name
        
        Returns:
            True if duplicate exists
        """
        try:
            query = f'"deck:{deck_name}" "Hanzi:{hanzi}"'
            note_ids = self._invoke('findNotes', {'query': query})
            return len(note_ids) > 0
        except AnkiConnectError as e:
            logger.error(f"Failed to check duplicate: {e}")
            return False
    
    def add_note(self, deck_name: str, model_name: str, fields: Dict[str, str],
                 audio_fields: Optional[Dict[str, bytes]] = None,
                 hsk_level: Optional[int] = None,
                 part_of_speech: Optional[str] = None) -> Optional[int]:
        """
        Add a new note to Anki with auto-tagging
        
        Args:
            deck_name: Target deck name
            model_name: Note type name
            fields: Dictionary of field_name: value
            audio_fields: Dictionary of field_name: audio_bytes for audio fields
            hsk_level: HSK level for auto-tagging
            part_of_speech: Part of speech for auto-tagging
        
        Returns:
            Note ID if successful, None otherwise
        """
        try:
            # Build tags
            tags = ['ChAnki']  # Always include ChAnki tag
            
            if hsk_level:
                tags.append(f'HSK-{hsk_level}')
            
            if part_of_speech:
                tags.append(part_of_speech.lower())
            
            # Prepare note
            note = {
                'deckName': deck_name,
                'modelName': model_name,
                'fields': fields,
                'options': {
                    'allowDuplicate': False
                },
                'tags': tags
            }
            
            # Add audio if provided
            if audio_fields:
                note['audio'] = []
                for field_name, audio_data in audio_fields.items():
                    note['audio'].append({
                        'data': audio_data.hex(),
                        'filename': f'{field_name}.mp3',
                        'fields': [field_name]
                    })
            
            note_id = self._invoke('addNote', {'note': note})
            logger.info(f"Added note with ID: {note_id}, tags: {tags}")
            return note_id
            
        except AnkiConnectError as e:
            logger.error(f"Failed to add note: {e}")
            return None
    
    def _get_card_css(self) -> str:
        """Get CSS for card styling with tone colors"""
        return """
        .card {
            font-family: 'Noto Sans SC', arial;
            font-size: 20px;
            text-align: center;
            color: #333;
            background-color: #fff;
        }
        
        .hanzi {
            font-size: 72px;
            font-weight: bold;
            margin: 20px 0;
        }
        
        .pinyin {
            font-size: 32px;
            color: #666;
            margin: 10px 0;
        }
        
        .tone1 { color: #e74c3c; }  /* Red - flat */
        .tone2 { color: #3498db; }  /* Blue - rising */
        .tone3 { color: #2ecc71; }  /* Green - falling-rising */
        .tone4 { color: #9b59b6; }  /* Purple - falling */
        .tone5 { color: #95a5a6; }  /* Gray - neutral */
        
        .english {
            font-size: 24px;
            color: #555;
            margin: 15px 0;
        }
        
        .sentence {
            font-size: 28px;
            margin: 20px 0;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }
        
        .cloze {
            font-weight: bold;
            color: #e74c3c;
        }
        """
    
    def _get_recall_card_front(self) -> str:
        """Get front template for Recall card (Card 1)"""
        return """
        <div class="hanzi">{{Hanzi}}</div>
        <div class="pinyin">{{Pinyin}}</div>
        {{Audio}}
        """
    
    def _get_recall_card_back(self) -> str:
        """Get back template for Recall card (Card 1)"""
        return """
        {{FrontSide}}
        <hr>
        <div class="english">{{English}}</div>
        <div class="sentence">{{Sentence_Hanzi}}</div>
        <div>{{Sentence_English}}</div>
        {{Sentence_Audio}}
        """
    
    def _get_cloze_card_front(self) -> str:
        """Get front template for Cloze card (Card 2)"""
        return """
        <div class="sentence">{{Sentence_Hanzi}}</div>
        {{Sentence_Audio}}
        <div class="pinyin" style="margin-top: 20px; font-size: 24px;">{{Pinyin}}</div>
        """
    
    def _get_cloze_card_back(self) -> str:
        """Get back template for Cloze card (Card 2)"""
        return """
        {{FrontSide}}
        <hr>
        <div class="hanzi">{{Hanzi}}</div>
        <div class="english">{{English}}</div>
        {{Audio}}
        <div class="sentence" style="margin-top: 20px;">{{Sentence_English}}</div>
        """
