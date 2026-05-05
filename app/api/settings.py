"""Settings API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.settings import AppSettings
from app.schemas.settings import SettingsUpdate, SettingsResponse
from app.services.service_cache import invalidate_settings, invalidate_ai
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
    if update_data.get('openai_api_key') == _AS.KEY_SET_SENTINEL:
        update_data.pop('openai_api_key')
    for field, value in update_data.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    invalidate_settings()
    if settings_update.openai_api_key is not None:
        invalidate_ai()

    return SettingsResponse(**settings.to_dict())


class OpenAITestRequest(BaseModel):
    """Request for testing OpenAI API key"""
    api_key: str


class OpenAITestResponse(BaseModel):
    """Response from OpenAI API key test"""
    success: bool
    message: str
    model_name: Optional[str] = None


@router.post("/settings/test-openai", response_model=OpenAITestResponse)
async def test_openai_connection(request: OpenAITestRequest):
    """
    Test OpenAI API key validity.

    Calls models.list() — read-only metadata, no token cost — so this
    endpoint never burns generation quota.
    """
    from openai import OpenAI

    if not request.api_key:
        return OpenAITestResponse(
            success=False,
            message="No API key provided"
        )

    try:
        client = OpenAI(api_key=request.api_key)
        models = list(client.models.list())

        # Confirm gpt-4o-mini (or the pinned MODEL) is reachable on this key
        from app.services.ai import MODEL
        ids = {m.id for m in models}
        if MODEL in ids:
            return OpenAITestResponse(
                success=True,
                message=f"✅ Connected to OpenAI ({MODEL})",
                model_name=MODEL,
            )
        # Key is valid but our pinned model isn't accessible — surface that
        return OpenAITestResponse(
            success=True,
            message=f"✅ Connected, but {MODEL} not in your model list ({len(ids)} models available)",
            model_name=None,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"OpenAI test failed: {error_msg}")
        if "incorrect api key" in error_msg.lower() or "invalid_api_key" in error_msg.lower():
            return OpenAITestResponse(
                success=False,
                message="❌ Invalid API key. Get one at platform.openai.com/api-keys."
            )
        if "rate_limit" in error_msg.lower():
            return OpenAITestResponse(
                success=False,
                message="❌ Rate limited. Try again in a moment."
            )
        return OpenAITestResponse(
            success=False,
            message=f"Connection failed: {error_msg}"
        )
