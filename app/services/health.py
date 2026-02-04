"""
Health Monitoring Service
Provides real-time status checks for all system components
"""

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    """Health status for a single component"""
    name: str
    status: str  # "healthy", "degraded", "down"
    message: str
    last_check: datetime
    latency_ms: Optional[float] = None


class HealthService:
    """
    Centralized health monitoring with caching
    Checks: Database, AnkiConnect, Gemini AI
    """
    
    def __init__(self, cache_ttl: int = 10):
        """
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 10s)
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, ComponentHealth] = {}
        self._last_full_check: Optional[datetime] = None
    
    def get_system_health(self, force_refresh: bool = False) -> Dict[str, dict]:
        """
        Get health status of all components
        
        Returns:
            Dictionary with health status for each component
        """
        now = datetime.now()
        
        # Check if cache is still valid
        if not force_refresh and self._last_full_check:
            if (now - self._last_full_check) < timedelta(seconds=self.cache_ttl):
                return self._cache_to_dict()
        
        # Perform fresh health checks
        self._check_database()
        self._check_anki()
        self._check_gemini()
        
        self._last_full_check = now
        return self._cache_to_dict()
    
    def _check_database(self):
        """Check database health"""
        start = time.time()
        
        try:
            from app.db.session import get_db_session
            from app.models.dictionary import DictionaryEntry
            
            db = next(get_db_session())
            
            # Simple count query to verify DB is responsive
            count = db.query(DictionaryEntry).count()
            latency = (time.time() - start) * 1000
            
            if count < 100000:
                self._cache['database'] = ComponentHealth(
                    name="Database",
                    status="degraded",
                    message=f"Dictionary has only {count:,} entries (Expected: >100,000)",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                self._cache['database'] = ComponentHealth(
                    name="Database",
                    status="healthy",
                    message=f"{count:,} entries loaded",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            
            db.close()
            
        except Exception as e:
            self._cache['database'] = ComponentHealth(
                name="Database",
                status="down",
                message=f"Error: {str(e)}",
                last_check=datetime.now()
            )
    
    def _check_anki(self):
        """Check AnkiConnect health"""
        start = time.time()
        
        try:
            from app.services.anki import AnkiService
            from app.config import settings
            
            anki = AnkiService(settings.anki_connect_url)
            
            if anki.check_connection():
                latency = (time.time() - start) * 1000
                deck_count = len(anki.get_deck_names())
                
                self._cache['anki'] = ComponentHealth(
                    name="AnkiConnect",
                    status="healthy",
                    message=f"{deck_count} deck(s) available",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                self._cache['anki'] = ComponentHealth(
                    name="AnkiConnect",
                    status="down",
                    message="Anki is not running",
                    last_check=datetime.now()
                )
        
        except Exception as e:
            self._cache['anki'] = ComponentHealth(
                name="AnkiConnect",
                status="down",
                message=f"Error: {str(e)}",
                last_check=datetime.now()
            )
    
    def _check_gemini(self):
        """Check Gemini AI health"""
        start = time.time()
        
        try:
            from app.services.gemini import GeminiService
            from app.config import settings
            from sqlalchemy.orm import Session
            from app.db.session import get_db_session
            from app.models.settings import AppSettings
            
            # Get API key from settings
            db = next(get_db_session())
            app_settings = db.query(AppSettings).first()
            
            api_key = None
            if app_settings and app_settings.gemini_api_key:
                api_key = app_settings.gemini_api_key
            elif settings.gemini_api_key:
                api_key = settings.gemini_api_key
            
            db.close()
            
            if not api_key:
                self._cache['gemini'] = ComponentHealth(
                    name="Gemini AI",
                    status="down",
                    message="API key not configured",
                    last_check=datetime.now()
                )
                return
            
            # Test connection
            gemini = GeminiService(api_key)
            if gemini.check_connection():
                latency = (time.time() - start) * 1000
                
                self._cache['gemini'] = ComponentHealth(
                    name="Gemini AI",
                    status="healthy",
                    message="API connected",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                self._cache['gemini'] = ComponentHealth(
                    name="Gemini AI",
                    status="down",
                    message="API key invalid or quota exceeded",
                    last_check=datetime.now()
                )
        
        except Exception as e:
            self._cache['gemini'] = ComponentHealth(
                name="Gemini AI",
                status="down",
                message=f"Error: {str(e)}",
                last_check=datetime.now()
            )
    
    def _cache_to_dict(self) -> Dict[str, dict]:
        """Convert cache to dictionary format"""
        return {
            key: {
                "name": health.name,
                "status": health.status,
                "message": health.message,
                "last_check": health.last_check.isoformat(),
                "latency_ms": health.latency_ms
            }
            for key, health in self._cache.items()
        }
