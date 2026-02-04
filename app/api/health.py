"""
Health API Endpoints
Provides real-time system status monitoring
"""

from fastapi import APIRouter
from app.services.health import HealthService
from app.db.init_db import check_and_download_dictionary
from pydantic import BaseModel
from typing import Dict


router = APIRouter(prefix="/api", tags=["health"])

# Global health service instance with 10s cache
health_service = HealthService(cache_ttl=10)


class HealthResponse(BaseModel):
    """Health check response"""
    overall_status: str  # "healthy", "degraded", "critical"
    components: Dict[str, dict]
    timestamp: str


class DatabaseStatusResponse(BaseModel):
    """Database status response"""
    ready: bool
    count: int
    message: str


@router.get("/health", response_model=HealthResponse)
async def check_health(force_refresh: bool = False):
    """
    Get real-time system health status
    
    Query params:
        force_refresh: Skip cache and force fresh checks (default: False)
    
    Returns:
        Health status of all components with latency metrics
    """
    import datetime
    
    components = health_service.get_system_health(force_refresh=force_refresh)
    
    # Determine overall status
    statuses = [comp["status"] for comp in components.values()]
    
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "down" for s in statuses):
        overall = "critical"
    else:
        overall = "degraded"
    
    return HealthResponse(
        overall_status=overall,
        components=components,
        timestamp=datetime.datetime.now().isoformat()
    )


@router.get("/db/status", response_model=DatabaseStatusResponse)
async def get_database_status():
    """
    Get database status and health metrics
    
    Returns:
        Database status with entry count
    """
    status = check_and_download_dictionary(auto_seed=False)
    return DatabaseStatusResponse(**status)


@router.post("/db/seed")
async def trigger_database_seed():
    """
    Manually trigger dictionary seeding
    
    Returns:
        Seeding progress and final status
    """
    status = check_and_download_dictionary(auto_seed=True)
    
    if status["ready"]:
        return {
            "success": True,
            "message": status["message"],
            "count": status["count"]
        }
    else:
        return {
            "success": False,
            "message": status["message"],
            "count": status["count"]
        }
