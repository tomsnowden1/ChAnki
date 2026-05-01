"""Pydantic schemas for settings API"""
from pydantic import BaseModel, Field
from typing import Optional


class SettingsUpdate(BaseModel):
    """Schema for updating settings"""
    anki_deck_name: Optional[str] = None
    anki_model_name: Optional[str] = None
    gemini_api_key: Optional[str] = None
    hsk_target_level: Optional[int] = Field(None, ge=1, le=6)
    tone_colors_enabled: Optional[bool] = None
    generate_audio: Optional[bool] = None
    strict_mode: Optional[bool] = None


class SettingsResponse(BaseModel):
    """Schema for settings response"""
    anki_deck_name: str
    anki_model_name: str
    gemini_api_key: str
    hsk_target_level: int
    tone_colors_enabled: bool
    generate_audio: bool
    strict_mode: bool = False
    updated_at: Optional[str] = None
