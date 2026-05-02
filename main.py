"""ChAnki v2 - FastAPI Main Application"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api import search, settings as settings_router, anki, health, sync
from app.config import settings as app_settings, DEFAULT_DEV_SYNC_SECRET
from app.middleware.rate_limit import limiter
from app.db.session import init_db
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ChAnki v2",
    description="Chinese to Anki Bridge - A modern web app for learning Chinese with Anki",
    version="2.0.0"
)

# Add global error handling middleware
from app.middleware.error_handler import ErrorHandlerMiddleware
app.add_middleware(ErrorHandlerMiddleware)

# --- Rate limiter (shared instance from app/middleware/rate_limit.py) ---
# Routes opt in via @limiter.limit("...") — see app/api/sync.py.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    logger.info("Initializing ChAnki v2.0...")

    # --- Production safety check ---------------------------------------
    # Refuse to boot if production is using the placeholder SYNC_SECRET —
    # it would mean the sync endpoints are effectively unauthenticated.
    if (
        app_settings.environment.lower() == "production"
        and app_settings.sync_secret == DEFAULT_DEV_SYNC_SECRET
    ):
        raise RuntimeError(
            "Refusing to start: ENVIRONMENT=production but SYNC_SECRET is the "
            "default development value. Set SYNC_SECRET to a real secret in "
            "Render env vars before redeploying."
        )

    from app.db.init_db import (
        initialize_database,
        check_and_download_dictionary,
        check_and_seed_sentences,
    )

    initialize_database()  # also calls setup_fts
    logger.info("✓ Database initialized")

    # Self-healing: Check and auto-seed dictionary if needed
    db_status = check_and_download_dictionary(auto_seed=True)
    logger.info(db_status["message"])

    # Sentence corpus must run after the dictionary seed so jieba filtering works
    sent_status = check_and_seed_sentences(auto_seed=True)
    logger.info(sent_status["message"])

    logger.info("✓ ChAnki v2.0 ready!")

# Include API routers
app.include_router(health.router)  # Health monitoring - first priority
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])  # Cloud-sync endpoints
app.include_router(search.router)
app.include_router(settings_router.router)
app.include_router(anki.router)

# Include UI helper routes
from app.api import anki_ui, duplicate, sentences
app.include_router(anki_ui.router)
app.include_router(duplicate.router)
app.include_router(sentences.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve frontend
@app.get("/")
async def serve_frontend():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")


@app.get("/guide")
async def serve_guide():
    """Serve the setup guide page"""
    return FileResponse("static/guide.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5173)
