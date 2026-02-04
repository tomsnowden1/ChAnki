"""Pydantic schemas for Anki API"""
from pydantic import BaseModel
from typing import Optional


class AddToAnkiRequest(BaseModel):
    """Request schema for adding to Anki"""
    hanzi: str
    pinyin: str
    definition: str
    hsk_level: Optional[int] = None
    part_of_speech: Optional[str] = None
    selected_sentence_index: int = 0  # Which of 3 AI-generated sentences to use




class AddToAnkiResponse(BaseModel):
    """Response schema for add to Anki"""
    success: bool
    status: str  # "success", "duplicate", "error"
    message: str
    note_id: Optional[int] = None


class AnkiStatusResponse(BaseModel):
    """Response schema for Anki connection status"""
    connected: bool
    model_exists: bool
    message: str
