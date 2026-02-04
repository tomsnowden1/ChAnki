"""Pydantic schemas for search API"""
from pydantic import BaseModel
from typing import List, Optional


class SearchRequest(BaseModel):
    """Request schema for search"""
    query: str


class DictionaryResult(BaseModel):
    """Single dictionary search result"""
    traditional: str
    simplified: str
    pinyin: str
    definitions: List[str]
    hsk_level: Optional[int] = None
    is_ai_generated: bool = False


class SearchResponse(BaseModel):
    """Response schema for search"""
    success: bool
    results: List[DictionaryResult]
    count: int
    is_ai_fallback: bool = False
