"""
FastAPI application for AI Compliance Agent
Production-ready with health checks, metrics, and graceful shutdown
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import signal
import sys
from typing import List, Optional
from contextlib import asynccontextmanager

from .routers import compliance_router, privacy_router, governance_router, remediation_router
from . import health, metrics
from ..core.compliance_engine import ComplianceEngine
from ..utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Global compliance engine instance
compliance_engine = None
_shutdown_event = asyncio.Event()


def setup_signal_handlers():
    """Setup graceful shutdown signal handlers"""

    def handle_shutdown(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received shutdown signal: {signal.Signals(signum).name}")
        _shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown"""
    global compliance_engine

    logger.info("🚀 Starting AI Compliance Agent API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Version: {settings.app_version}")

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    # Initialize compliance engine
    try:
        compliance_engine = ComplianceEngine()
        await compliance_engine.initialize()
        logger.info("✅ Compliance engine initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize compliance engine: {e}")
        raise

    yield

    # Graceful shutdown
    logger.info("🛑 Initiating graceful shutdown...")

    # Cleanup tasks
    cleanup_tasks = []

    # Close compliance engine
    if compliance_engine:
        try:
            if hasattr(compliance_engine, 'close'):
                cleanup_tasks.append(compliance_engine.close())
            logger.info("✅ Compliance engine shutdown complete")
        except Exception as e:
            logger.error(f"❌ Error closing compliance engine: {e}")

    # Wait for cleanup with timeout
    if cleanup_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*cleanup_tasks, return_exceptions=True),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("⚠️  Cleanup timeout exceeded, forcing shutdown")

    logger.info("👋 Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered compliance checking for PDPA, international data privacy, and data governance",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production() or settings.debug else None,
    redoc_url="/redoc" if not settings.is_production() or settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
)

# Add metrics middleware if enabled
if settings.metrics_enabled:
    app.add_middleware(metrics.MetricsMiddleware)


# Dependency to get compliance engine
async def get_compliance_engine() -> ComplianceEngine:
    """Dependency to get the compliance engine instance"""
    if compliance_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Compliance engine not initialized"
        )
    return compliance_engine


# Include health check and metrics routers
app.include_router(health.router)
if settings.metrics_enabled:
    app.include_router(metrics.router)

# Include business logic routers
app.include_router(
    compliance_router.router,
    prefix="/api/v1/compliance",
    tags=["compliance"]
)
app.include_router(
    privacy_router.router,
    prefix="/api/v1/privacy",
    tags=["privacy"]
)
app.include_router(
    governance_router.router,
    prefix="/api/v1/governance",
    tags=["governance"]
)
app.include_router(
    remediation_router.router,
    tags=["remediation"]
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - service information"""
    return {
        "message": f"{settings.app_name} API",
        "version": settings.app_version,
        "environment": settings.environment,
        "description": "AI-powered compliance checking for PDPA, international data privacy, and data governance",
        "docs_url": "/docs" if not settings.is_production() or settings.debug else None,
        "health_check": "/health",
        "readiness_check": "/health/ready",
        "liveness_check": "/health/live",
        "metrics": "/metrics" if settings.metrics_enabled else None
    }


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with detailed logging"""
    logger.error(
        f"Unhandled exception",
        exc_info=exc,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None
        }
    )

    # Don't expose internal errors in production
    if settings.is_production() and not settings.debug:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )