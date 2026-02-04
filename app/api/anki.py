"""Anki API endpoints"""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.services.anki import AnkiService, AnkiConnectError
from app.services.gemini import GeminiService
from app.services.audio import AudioService
from app.schemas.anki import AddToAnkiRequest, AddToAnkiResponse, AnkiStatusResponse
from app.config import settings as app_settings
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["anki"])



@router.post("/get-decks")
async def get_decks():
    """Fetch list of deck names from Anki"""
    anki = AnkiService(app_settings.anki_connect_url)
    if not anki.check_connection():
        return {"success": False, "decks": [], "message": "Anki is not connected"}
        
    try:
        decks = anki.get_deck_names()
        return {"success": True, "decks": decks}
    except Exception as e:
        logger.error(f"Failed to fetch decks: {e}")
        return {"success": False, "decks": [], "message": str(e)}


@router.get("/anki/status", response_model=AnkiStatusResponse)
async def check_anki_status(db: Session = Depends(get_db_session)):
    """Check AnkiConnect connection and model status"""
    anki = AnkiService(app_settings.anki_connect_url)
    
    # Get model name from settings
    settings = db.query(AppSettings).first()
    model_name = settings.anki_model_name if settings else "ChAnki-Advanced"
    
    connected = anki.check_connection()
    
    if not connected:
        return AnkiStatusResponse(
            connected=False,
            model_exists=False,
            message="AnkiConnect is not accessible. Please ensure Anki is running."
        )
    
    # Check if model exists
    model_exists = model_name in anki.model_names()
    
    return AnkiStatusResponse(
        connected=True,
        model_exists=model_exists,
        message=f"Connected. Model '{model_name}' {'exists' if model_exists else 'will be created'}."
    )


@router.post("/add-to-anki", response_model=AddToAnkiResponse)
async def add_to_anki(
    request: AddToAnkiRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """
    Add a word to Anki with generated sentence and audio
    
    Process:
    1. Check for duplicates
    2. Generate example sentence (Gemini)
    3. Generate audio (edge-tts)
    4. Create note type if needed
    5. Add note to Anki
    """
    # Get settings
    settings = db.query(AppSettings).first()
    if not settings:
        settings = AppSettings()
    
    # Initialize services
    anki = AnkiService(app_settings.anki_connect_url)
    gemini =  GeminiService(settings.gemini_api_key or app_settings.gemini_api_key)
    audio = AudioService()
    
    try:
        # Step 1: Check connection
        if not anki.check_connection():
            return AddToAnkiResponse(
                success=False,
                status="error",
                message="AnkiConnect is not running. Please start Anki."
            )
        
        # Step 2: Check duplicates
        if anki.check_duplicate(request.hanzi, settings.anki_deck_name):
            return AddToAnkiResponse(
                success=False,
                status="duplicate",
                message=f"'{request.hanzi}' already exists in your Anki deck."
            )
        
        # Step 3: Ensure model exists
        if not anki.ensure_model_exists(settings.anki_model_name):
            return AddToAnkiResponse(
                success=False,
                status="error",
                message="Failed to create or verify Anki note type."
            )
        
        # Step 4: Generate 3 sentences
        logger.info(f"Generating 3 sentences for {request.hanzi}")
        sentences = gemini.generate_sentences(
            request.hanzi,
            request.pinyin,
            request.definition,
            settings.hsk_target_level
        )
        
        # Select the sentence chosen by user (default: 0)
        selected_idx = request.selected_sentence_index
        if selected_idx < 0 or selected_idx >= len(sentences):
            selected_idx = 0
        
        selected_sentence = sentences[selected_idx]
        
        # Store the other 2 sentences for reference
        other_sentences = [s for i, s in enumerate(sentences) if i != selected_idx]

        
        # Step 5: Generate audio (if enabled)
        audio_fields = {}
        if settings.generate_audio:
            logger.info("Generating audio...")
            word_audio = audio.generate_audio(request.hanzi)
            sentence_audio = audio.generate_audio(selected_sentence['sentence_simplified'])

            
            if word_audio:
                audio_fields['Audio'] = word_audio
            if sentence_audio:
                audio_fields['Sentence_Audio'] = sentence_audio
        
        # Step 6: Prepare fields
        fields = {
            'Hanzi': request.hanzi,
            'Pinyin': request.pinyin,
            'English': request.definition,
            'Sentence_Hanzi': selected_sentence['sentence_simplified'],
            'Sentence_English': selected_sentence['sentence_english'],
            'Extra_Examples': json.dumps(other_sentences, ensure_ascii=False)
        }
        
        # Step 7: Add note with tags
        note_id = anki.add_note(
            deck_name=settings.anki_deck_name,
            model_name=settings.anki_model_name,
            fields=fields,
            audio_fields=audio_fields if audio_fields else None,
            hsk_level=request.hsk_level,  # Pass HSK level for tagging
            part_of_speech=request.part_of_speech  # Pass POS for tagging
        )
        
        if note_id:
            tags_list = ['ChAnki']
            if request.hsk_level:
                tags_list.append(f'HSK-{request.hsk_level}')
            if request.part_of_speech:
                tags_list.append(request.part_of_speech)
            
            return AddToAnkiResponse(
                success=True,
                status="success",
                message=f"Successfully added '{request.hanzi}' to Anki! Tags: {', '.join(tags_list)}",
                note_id=note_id
            )
        else:
            return AddToAnkiResponse(
                success=False,
                status="error",
                message="Failed to add note to Anki."
            )
            
    except AnkiConnectError as e:
        logger.error(f"AnkiConnect error: {e}")
        return AddToAnkiResponse(
            success=False,
            status="error",
            message=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return AddToAnkiResponse(
            success=False,
            status="error",
            message=f"An error occurred: {str(e)}"
        )
