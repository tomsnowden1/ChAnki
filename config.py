import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for ChAnki application"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # AnkiConnect settings
    ANKI_CONNECT_URL = os.environ.get('ANKI_CONNECT_URL', 'http://localhost:8765')
    ANKI_DECK_NAME = os.environ.get('ANKI_DECK_NAME', 'Chinese::Vocabulary')
    ANKI_NOTE_TYPE = os.environ.get('ANKI_NOTE_TYPE', 'Chinese-Cloze')
    
    # LLM settings (Ollama)
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama2')
    
    # Dictionary settings
    CEDICT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cedict_ts.u8')
