"""
API endpoint to generate 3 sentences for preview (before adding to Anki).

Tatoeba is the primary source; Gemini is the fallback when Tatoeba lacks
enough hits for the queried word.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.services.service_cache import get_gemini, get_settings, get_sentence_service
from app.config import settings as env_settings
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
    """Generate 3 example sentences. Tries Tatoeba first, then Gemini."""
    try:
        settings = get_settings(db)
        gemini = None
        api_key = (settings.gemini_api_key if settings else "") or env_settings.gemini_api_key
        if api_key:
            gemini = get_gemini(api_key)

        service = get_sentence_service(db, gemini)
        sentences = service.find_sentences(
            request.hanzi,
            request.pinyin,
            request.definition,
            request.hsk_level or 3,
        )

        if not sentences:
            return GenerateSentencesResponse(
                success=False,
                sentences=[],
                message=(
                    "No Tatoeba match and no Gemini key configured. "
                    "Add a Gemini key in Settings to enable AI fallback."
                    if gemini is None
                    else "No sentences found."
                ),
            )

        return GenerateSentencesResponse(success=True, sentences=sentences)

    except Exception as e:
        return GenerateSentencesResponse(
            success=False,
            sentences=[],
            message=f"Error: {str(e)}",
        )
