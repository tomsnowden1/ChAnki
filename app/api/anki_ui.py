"""AnkiConnect dropdown endpoints for dynamic UI"""
from fastapi import APIRouter
from app.services.anki import AnkiService, AnkiConnectError
from app.config import settings as app_settings
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api/anki", tags=["anki-ui"])


class DeckNamesResponse(BaseModel):
    """Response schema for deck names"""
    success: bool
    decks: List[str]
    message: str = ""


class ModelNamesResponse(BaseModel):
    """Response schema for model names"""
    success: bool
    models: List[str]
    message: str = ""


@router.get("/decks", response_model=DeckNamesResponse)
async def get_deck_names():
    """Get list of all Anki deck names for dropdown"""
    anki = AnkiService(app_settings.anki_connect_url)
    
    try:
        if not anki.check_connection():
            return DeckNamesResponse(
                success=False,
                decks=[],
                message="AnkiConnect not running. Please start Anki."
            )
        
        # Get deck names using AnkiConnect
        decks = anki._invoke('deckNames')
        
        return DeckNamesResponse(
            success=True,
            decks=sorted(decks) if decks else [],
            message=f"Found {len(decks)} decks"
        )
    
    except AnkiConnectError as e:
        return DeckNamesResponse(
            success=False,
            decks=[],
            message=str(e)
        )


@router.get("/models", response_model=ModelNamesResponse)
async def get_model_names():
    """Get list of all Anki note type names for dropdown"""
    anki = AnkiService(app_settings.anki_connect_url)
    
    try:
        if not anki.check_connection():
            return ModelNamesResponse(
                success=False,
                models=[],
                message="AnkiConnect not running. Please start Anki."
            )
        
        models = anki.model_names()
        
        return ModelNamesResponse(
            success=True,
            models=sorted(models) if models else [],
            message=f"Found {len(models)} note types"
        )
    
    except AnkiConnectError as e:
        return ModelNamesResponse(
            success=False,
            models=[],
            message=str(e)
        )
