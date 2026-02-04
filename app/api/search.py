"""Search API endpoints"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.services.dictionary import DictionaryService
from app.services.gemini import GeminiService
from app.schemas.search import SearchResponse, DictionaryResult

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_dictionary(
    q: str = Query(..., description="Search query"),
    db: Session = Depends(get_db_session)
):
    """
    Search the dictionary for Chinese words with AI fallback
    
    Supports:
    - English → Chinese (with AI fallback if not in DB)
    - Pinyin → Chinese
    - Hanzi → English/Pinyin
    """
    dict_service = DictionaryService(db)
    
    # Get Gemini service for AI fallback
    settings = db.query(AppSettings).first()
    gemini = GeminiService(settings.gemini_api_key if settings else "")
    
    # Use AI fallback method
    entries, is_ai = dict_service.search_with_ai_fallback(q, gemini, limit=20)
    
    results = [
        DictionaryResult(
            traditional=entry.traditional,
            simplified=entry.simplified,
            pinyin=entry.pinyin,
            definitions=entry.to_dict()['definitions'],
            hsk_level=entry.hsk_level,
            is_ai_generated=is_ai
        )
        for entry in entries
    ]
    
    return SearchResponse(
        success=True,
        results=results,
        count=len(results),
        is_ai_fallback=is_ai
    )
