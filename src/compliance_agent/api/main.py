"""
FastAPI application for AI Compliance Agent
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager

from .routers import compliance_router, privacy_router, governance_router, remediation_router
from ..core.compliance_engine import ComplianceEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Global compliance engine instance
compliance_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global compliance_engine
    logger.info("Starting AI Compliance Agent API")
    
    # Initialize compliance engine
    compliance_engine = ComplianceEngine()
    await compliance_engine.initialize()
    
    yield
    
    logger.info("Shutting down AI Compliance Agent API")


# Create FastAPI application
app = FastAPI(
    title="AI Compliance Agent",
    description="AI-powered compliance checking for PDPA, international data privacy, and data governance",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get compliance engine
async def get_compliance_engine() -> ComplianceEngine:
    """Dependency to get the compliance engine instance"""
    if compliance_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Compliance engine not initialized"
        )
    return compliance_engine


# Include routers
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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Compliance Agent API",
        "version": "1.0.0",
        "description": "AI-powered compliance checking for PDPA, international data privacy, and data governance"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ai-compliance-agent",
        "engine_initialized": compliance_engine is not None
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )