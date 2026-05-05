"""
Global Error Handling Middleware
Catches all unhandled exceptions and returns clean JSON responses
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler that catches all exceptions
    Returns clean, actionable JSON responses instead of HTML error pages
    """
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as exc:
            # Let FastAPI handle HTTP exceptions normally
            raise exc
            
        except Exception as exc:
            # Log the full error for debugging
            logger.error(f"Unhandled exception on {request.method} {request.url.path}")
            logger.error(traceback.format_exc())
            
            # Return clean JSON response with suggestion
            error_message, suggestion = self._get_error_details(exc)
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": error_message,
                    "suggestion": suggestion,
                    "path": str(request.url.path),
                    "type": exc.__class__.__name__
                }
            )
    
    def _get_error_details(self, exc: Exception) -> tuple[str, str]:
        """
        Get user-friendly error message and actionable suggestion
        
        Returns:
            (error_message, suggestion)
        """
        error_type = exc.__class__.__name__
        error_str = str(exc)
        
        # Database errors
        if "database" in error_str.lower() or "sqlite" in error_str.lower():
            return (
                "Database connection error",
                "The database may be corrupt. Try `POST /api/db/seed` to rebuild it."
            )
        
        # OpenAI API errors
        s = error_str.lower()
        if "openai" in s or "api_key" in s or "rate_limit" in s or "invalid_api_key" in s:
            return (
                "AI service unavailable",
                "Check your OpenAI API key in Settings and ensure it is valid."
            )
        
        # AnkiConnect errors
        if "anki" in error_str.lower() or "8765" in error_str:
            return (
                "Anki is not responding",
                "Ensure Anki is running and AnkiConnect add-on is installed."
            )
        
        # File not found errors
        if "filenotfound" in error_type.lower() or "no such file" in error_str.lower():
            return (
                "Required file not found",
                "Ensure all dependencies are installed. Run `POST /api/db/seed` if dictionary is missing."
            )
        
        # Module import errors
        if "modulenotfound" in error_type.lower() or "import" in error_str.lower():
            return (
                "Missing dependency",
                "Run: `pip install -r requirements.txt` in your virtual environment."
            )
        
        # Generic fallback
        return (
            f"{error_type}: {error_str}",
            "Check the server logs for more details or run `GET /api/health` to diagnose."
        )
