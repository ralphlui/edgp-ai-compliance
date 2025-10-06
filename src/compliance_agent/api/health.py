"""
Health check and readiness probe endpoints
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import Dict, Optional
import time
import psutil
from datetime import datetime

from config.settings import settings

router = APIRouter(tags=["Health"])

# Track service start time
_start_time = time.time()


class HealthStatus(BaseModel):
    """Health check response model"""
    status: str
    service: str = "AI Compliance Agent"
    timestamp: datetime
    uptime_seconds: float
    version: str
    environment: str


class ReadinessStatus(BaseModel):
    """Readiness check response model"""
    ready: bool
    checks: Dict[str, bool]
    timestamp: datetime


class LivenessStatus(BaseModel):
    """Liveness check response model"""
    alive: bool
    timestamp: datetime
    memory_usage_percent: float
    cpu_usage_percent: float


@router.get("/health", response_model=HealthStatus, status_code=status.HTTP_200_OK)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint
    Returns service status and uptime
    """
    uptime = time.time() - _start_time

    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow(),
        uptime_seconds=uptime,
        version=settings.app_version,
        environment=settings.environment
    )


@router.get("/health/ready", response_model=ReadinessStatus)
async def readiness_check(response: Response) -> ReadinessStatus:
    """
    Readiness probe - checks if service is ready to accept traffic
    Validates that all dependencies are available
    """
    checks = {
        "api": True,  # If we got here, API is running
        "config": _check_config(),
    }

    # Check if OpenAI API key is configured (if AI analysis is enabled)
    if settings.enable_ai_analysis:
        checks["openai"] = bool(settings.openai_api_key)

    # Check if AWS credentials are configured (if remediation is enabled)
    if settings.remediation_agent_enabled:
        checks["aws"] = bool(settings.aws_access_key_id) or settings.environment == "development"

    all_ready = all(checks.values())

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessStatus(
        ready=all_ready,
        checks=checks,
        timestamp=datetime.utcnow()
    )


@router.get("/health/live", response_model=LivenessStatus)
async def liveness_check(response: Response) -> LivenessStatus:
    """
    Liveness probe - checks if service is alive
    Monitors resource usage
    """
    try:
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Consider unhealthy if memory > 95% or CPU > 95% sustained
        is_healthy = memory_percent < 95 and cpu_percent < 95

        if not is_healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return LivenessStatus(
            alive=is_healthy,
            timestamp=datetime.utcnow(),
            memory_usage_percent=memory_percent,
            cpu_usage_percent=cpu_percent
        )
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return LivenessStatus(
            alive=False,
            timestamp=datetime.utcnow(),
            memory_usage_percent=0.0,
            cpu_usage_percent=0.0
        )


def _check_config() -> bool:
    """Check if critical configuration is valid"""
    try:
        # Validate required configuration
        if settings.is_production():
            missing = settings.validate_required_secrets()
            return len(missing) == 0
        return True
    except Exception:
        return False
