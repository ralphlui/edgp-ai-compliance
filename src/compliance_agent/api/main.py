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
from datetime import datetime, timedelta

from .routers import compliance_router, privacy_router, governance_router, remediation_router
from . import health, metrics
from ..core.compliance_engine import ComplianceEngine
from ..international_ai_agent import InternationalAIComplianceAgent
from ..utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Global compliance engine instance
compliance_engine = None
background_compliance_agent = None
background_task = None
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
    global compliance_engine, background_compliance_agent, background_task

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

    # Initialize and start automatic background compliance scanning
    try:
        background_compliance_agent = InternationalAIComplianceAgent()
        await background_compliance_agent.initialize()
        
        # Start background compliance scanning every 5 minutes
        async def run_periodic_compliance():
            """Background task to run compliance scanning every 5 minutes"""
            scan_count = 0
            while True:
                try:
                    scan_count += 1
                    start_time = datetime.now()
                    
                    # START log as requested by user
                    print(f"INFO: Compliance Schedule jobs is running at 5mins - START - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Scan the records on Database retrieved
                    print("INFO: ---scan the records on Database retrieved")
                    violations = await background_compliance_agent.scan_customer_compliance()
                    
                    # Check the compliance
                    print("INFO: ---check the compliance")
                    
                    # Found violation and logs what and how are violate
                    if violations:
                        total_violations = len(violations)
                        print(f"INFO: ⚠️  COMPLIANCE VIOLATIONS DETECTED: {total_violations} records found")
                        print(f"INFO: ---found violation - {total_violations} records")
                        print("INFO: ---logs what and how are violate")
                        
                        for i, violation in enumerate(violations, 1):
                            print(f"INFO: VIOLATION #{i}/{total_violations}: Customer ID {violation.customer_id} (Hash: {violation.customer_hash}) violates {violation.framework} - {violation.violation_type} (Severity: {violation.severity})")
                            print(f"INFO:   Description: {violation.description}")
                            print(f"INFO:   Data age: {violation.data_age_days} days (exceeds limit by {violation.data_age_days - violation.retention_limit_days} days)")
                            
                            # Call remediation_agent endpoint to pass the violated data
                            print("INFO: ---Call remediation_agent endpoint to pass the violated data")
                            
                            # Prepare remediation data in the required format
                            remediation_data = {
                                "id": f"customer_{violation.customer_id}",  # Use actual database ID
                                "action": "delete",
                                "message": f"Customer data retention exceeded by {violation.data_age_days - violation.retention_limit_days} days under GDPR Article 17",
                                "field_name": "created_date",  # Actual violated database field
                                "domain_name": "customer",
                                "framework": "gdpr_eu",
                                "urgency": "high" if violation.severity == "HIGH" else "medium",
                                "user_id": violation.workflow_tracker_id or f"workflow_tracker_{violation.customer_id}"  # Use actual workflow_tracker_id from database
                            }
                            
                            print(f"INFO: 📤 Sending remediation data: {remediation_data}")
                            
                            # Enhanced logging for debugging - print the complete request record
                            print("INFO: " + "=" * 80)
                            print("INFO: 📋 MAIN FLOW - COMPLETE REMEDIATION REQUEST RECORD")
                            print("INFO: " + "=" * 80)
                            print(f"INFO: 🆔 Request ID: {remediation_data['id']}")
                            print(f"INFO: ⚡ Action: {remediation_data['action']}")
                            print(f"INFO: 📝 Message: {remediation_data['message']}")
                            print(f"INFO: 🏷️  Field Name: {remediation_data['field_name']}")
                            print(f"INFO: 🏢 Domain Name: {remediation_data['domain_name']}")
                            print(f"INFO: ⚖️  Framework: {remediation_data['framework']}")
                            print(f"INFO: 🚨 Urgency: {remediation_data['urgency']}")
                            print(f"INFO: 👤 User ID: {remediation_data['user_id']}")
                            print("INFO: 📊 Violation Details:")
                            print(f"INFO:   • Customer ID: {violation.customer_id}")
                            print(f"INFO:   • Customer Hash: {violation.customer_hash}")
                            print(f"INFO:   • Violation Type: {violation.violation_type}")
                            print(f"INFO:   • Framework: {violation.framework}")
                            print(f"INFO:   • Severity: {violation.severity}")
                            print(f"INFO:   • Data Age: {violation.data_age_days} days")
                            print(f"INFO:   • Retention Limit: {violation.retention_limit_days} days")
                            print(f"INFO:   • Excess Days: {violation.data_age_days - violation.retention_limit_days} days")
                            print(f"INFO:   • Confidence Score: {violation.confidence_score}")
                            print(f"INFO:   • Region: {violation.region}")
                            print("INFO: " + "=" * 80)
                            
                            # Call remediation service
                            try:
                                if hasattr(background_compliance_agent, 'remediation_service') and background_compliance_agent.remediation_service:
                                    success = await background_compliance_agent.remediation_service.trigger_remediation(remediation_data)
                                    if success:
                                        print(f"INFO: ✅ Remediation triggered successfully for customer ID {violation.customer_id}")
                                        print(f"INFO: 📨 Data should be sent to SQS DLQ: dev-remediation-workflow-dlq")
                                    else:
                                        print(f"INFO: ❌ Remediation failed for customer ID {violation.customer_id}")
                                else:
                                    print("INFO: ⚠️ Remediation service not available")
                            except Exception as e:
                                print(f"INFO: ❌ Error calling remediation endpoint: {e}")
                        
                        # Summary of violations processed
                        print(f"INFO: 📊 VIOLATION SUMMARY: {total_violations} records processed for remediation")
                    else:
                        print("INFO: ✅ No compliance violations found")
                    
                    end_time = datetime.now()
                    
                    # END log as requested by user
                    print(f"INFO: Compliance Schedule jobs is running at 5mins - END - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Wait for 5 minutes (300 seconds)
                    await asyncio.sleep(300)
                    
                except asyncio.CancelledError:
                    logger.info("🛑 Periodic compliance scanning cancelled")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in periodic compliance scan: {e}")
                    logger.error(f"🔄 Retrying in 1 minute...")
                    # Wait 1 minute before retrying on error
                    await asyncio.sleep(60)
        
        background_task = asyncio.create_task(run_periodic_compliance())
        logger.info("✅ Background compliance scanning started (every 5 minutes)")
        logger.info("🔔 Enhanced logging enabled - you'll see detailed scan reports every 5 minutes")
        logger.info("📅 Watch for 'AUTOMATIC COMPLIANCE SCAN #X' messages in the logs")
    except Exception as e:
        logger.error(f"⚠️ Failed to start background compliance scanning: {e}")
        logger.info("API will continue without automatic scanning")
        background_compliance_agent = None
        background_task = None

    yield

    # Graceful shutdown
    logger.info("🛑 Initiating graceful shutdown...")

    # Cleanup tasks
    cleanup_tasks = []

    # Stop background compliance scanning
    if background_task:
        try:
            background_task.cancel()
            try:
                await background_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Background compliance scanning stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping background scanning: {e}")

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