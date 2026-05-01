"""Search API endpoints"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.services.dictionary import DictionaryService
from app.services.service_cache import get_gemini, get_settings
from app.schemas.search import SearchResponse, DictionaryResult

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_dictionary(
    q: str = Query(..., description="Search query"),
    db: Session = Depends(get_db_session)
):
    """Search the dictionary for Chinese words with AI fallback."""
    dict_service = DictionaryService(db)

    settings = get_settings(db)
    gemini = get_gemini(settings.gemini_api_key if settings else "")

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
