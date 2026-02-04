"""ChAnki v2 - FastAPI Main Application"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import search, settings, anki, health
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

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    logger.info("Initializing ChAnki v2.0...")
    from app.db.init_db import initialize_database, check_and_download_dictionary
    
    initialize_database()
    logger.info("✓ Database initialized")
    
    # Self-healing: Check and auto-seed dictionary if needed
    db_status = check_and_download_dictionary(auto_seed=True)
    logger.info(db_status["message"])
    
    logger.info("✓ ChAnki v2.0 ready!")

# Include API routers
app.include_router(health.router)  # Health monitoring - first priority
app.include_router(search.router)
app.include_router(settings.router)
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
