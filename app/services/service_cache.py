"""
Module-level singletons for services that are expensive to construct.

GeminiService: recreated only when the API key changes.
AppSettings:   cached with a 30s TTL; invalidated immediately on PUT /settings.
"""
import time
from threading import Lock
from typing import Optional

_lock = Lock()

# --- Gemini ---
_gemini = None
_gemini_key: str = ''


def get_gemini(api_key: str):
    """Return a cached GeminiService, rebuilding only when the key changes."""
    global _gemini, _gemini_key
    with _lock:
        if _gemini is None or api_key != _gemini_key:
            from app.services.gemini import GeminiService
            _gemini = GeminiService(api_key)
            _gemini_key = api_key
        return _gemini


def invalidate_gemini():
    global _gemini, _gemini_key
    with _lock:
        _gemini = None
        _gemini_key = ''


# --- AppSettings ---
_settings = None
_settings_ts: float = 0.0
_SETTINGS_TTL = 30.0  # seconds


def get_settings(db):
    """Return cached AppSettings, refreshing after TTL expires.

    Returns None (never raises) so callers that do
    ``(settings.x if settings else default)`` are safe even when a schema
    migration hasn't completed yet.
    """
    global _settings, _settings_ts
    with _lock:
        if _settings is None or (time.monotonic() - _settings_ts) > _SETTINGS_TTL:
            from app.models.settings import AppSettings
            try:
                _settings = db.query(AppSettings).first()
                _settings_ts = time.monotonic()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"get_settings query failed (schema migration pending?): {e}"
                )
                try:
                    db.rollback()
                except Exception:
                    pass
                return None
        return _settings


def invalidate_settings():
    global _settings
    with _lock:
        _settings = None


# --- SentenceService ---
def get_sentence_service(db, gemini=None):
    """Factory for SentenceService.

    A fresh instance is built per request because the SQLAlchemy session is
    request-scoped. The injected GeminiService is itself cached above.
    """
    from app.services.sentence_service import SentenceService
    return SentenceService(db, gemini)
