"""Duplicate check endpoint for UI"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.services.anki import AnkiService
from app.config import settings as app_settings
from pydantic import BaseModel

router = APIRouter(prefix="/api/duplicate", tags=["duplicate"])


class DuplicateCheckRequest(BaseModel):
    """Request for duplicate check"""
    hanzi: str


class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check"""
    is_duplicate: bool
    message: str


@router.post("/check", response_model=DuplicateCheckResponse)
async def check_duplicate(
    request: DuplicateCheckRequest,
    db: Session = Depends(get_db_session)
):
    """Check if a word already exists in Anki"""
    settings = db.query(AppSettings).first()
    
    if not settings:
        return DuplicateCheckResponse(
            is_duplicate=False,
            message="Settings not configured"
        )
    
    anki = AnkiService(app_settings.anki_connect_url)
    
    try:
        if not anki.check_connection():
            return DuplicateCheckResponse(
                is_duplicate=False,
                message="AnkiConnect not running"
            )
        
        is_dup = anki.check_duplicate(request.hanzi, settings.anki_deck_name)
        
        return DuplicateCheckResponse(
            is_duplicate=is_dup,
            message="Already in deck" if is_dup else "Ready to add"
        )
    
    except Exception as e:
        return DuplicateCheckResponse(
            is_duplicate=False,
            message=f"Error checking: {str(e)}"
        )
