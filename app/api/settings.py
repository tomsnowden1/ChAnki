"""Settings API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.schemas.settings import SettingsUpdate, SettingsResponse
from app.services.service_cache import invalidate_settings, invalidate_gemini
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db_session)):
    """Get current application settings"""
    settings = db.query(AppSettings).first()
    
    if not settings:
        # Create default settings if they don't exist
        settings = AppSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return SettingsResponse(**settings.to_dict())


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    settings_update: SettingsUpdate,
    db: Session = Depends(get_db_session)
):
    """Update application settings"""
    settings = db.query(AppSettings).first()
    
    if not settings:
        settings = AppSettings()
        db.add(settings)
    
    update_data = settings_update.model_dump(exclude_unset=True)
    # Never overwrite the real key with the masked sentinel
    from app.models.settings import AppSettings as _AS
    if update_data.get('gemini_api_key') == _AS.KEY_SET_SENTINEL:
        update_data.pop('gemini_api_key')
    for field, value in update_data.items():
        setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)

    invalidate_settings()
    if settings_update.gemini_api_key is not None:
        invalidate_gemini()

    return SettingsResponse(**settings.to_dict())


class GeminiTestRequest(BaseModel):
    """Request for testing Gemini API key"""
    api_key: str


class GeminiTestResponse(BaseModel):
    """Response from Gemini API key test"""
    success: bool
    message: str
    model_name: Optional[str] = None


@router.post("/settings/test-gemini", response_model=GeminiTestResponse)
async def test_gemini_connection(request: GeminiTestRequest):
    """
    Test Gemini API key validity
    
    Attempts to list models to verify the key works
    """
    import google.generativeai as genai
    
    if not request.api_key:
        return GeminiTestResponse(
            success=False,
            message="No API key provided"
        )
    
    try:
        # Configure with provided key
        genai.configure(api_key=request.api_key)
        
        # Try to list models as a validation test
        models = list(genai.list_models())
        model_names = [m.name for m in models if 'gemini' in m.name.lower()]
        
        if model_names:
            return GeminiTestResponse(
                success=True,
                message="✅ Connected to Gemini Flash!",
                model_name="gemini-1.5-flash"
            )
        else:
            return GeminiTestResponse(
                success=False,
                message="No Gemini models available for this key"
            )
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini test failed: {error_msg}")
        if "API_KEY_INVALID" in error_msg or "invalid" in error_msg.lower():
            return GeminiTestResponse(
                success=False,
                message="❌ Invalid API Key. Please check your Google AI Studio settings."
            )
        else:
            return GeminiTestResponse(
                success=False,
                message=f"Connection failed: {error_msg}"
            )
