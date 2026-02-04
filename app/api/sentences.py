"""
API endpoint to generate 3 sentences for preview (before adding to Anki)
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.services.gemini import GeminiService
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter(prefix="/api", tags=["sentences"])


class GenerateSentencesRequest(BaseModel):
    hanzi: str
    pinyin: str
    definition: str
    hsk_level: Optional[int] = 3


class GenerateSentencesResponse(BaseModel):
    success: bool
    sentences: List[Dict[str, str]]
    message: Optional[str] = None


@router.post("/generate-sentences", response_model=GenerateSentencesResponse)
async def generate_sentences(
    request: GenerateSentencesRequest,
    db: Session = Depends(get_db_session)
):
    """Generate 3 example sentences for preview"""
    try:
        # Get settings for API key
        settings = db.query(AppSettings).first()
        if not settings or not settings.gemini_api_key:
            return GenerateSentencesResponse(
                success=False,
                sentences=[],
                message="Gemini API key not configured"
            )
        
        # Generate sentences
        gemini = GeminiService(settings.gemini_api_key)
        sentences = gemini.generate_sentences(
            request.hanzi,
            request.pinyin,
            request.definition,
            request.hsk_level
        )
        
        return GenerateSentencesResponse(
            success=True,
            sentences=sentences
        )
        
    except Exception as e:
        return GenerateSentencesResponse(
            success=False,
            sentences=[],
            message=f"Error: {str(e)}"
        )
