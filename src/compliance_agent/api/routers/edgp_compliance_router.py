"""
EDGP Master Data Compliance API Router

FastAPI router for EDGP master data compliance operations including:
- Data retention scanning
- Compliance violation detection  
- Automated remediation workflows
- Compliance reporting and monitoring
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel, Field

# Use absolute imports to avoid import errors
from src.compliance_agent.models.edgp_models import (
    DataRetentionAnalysis, 
    ComplianceViolationRecord
)
from src.compliance_agent.models.compliance_models import (
    ComplianceFramework, 
    RiskLevel,
    ComplianceStatus
)
from src.compliance_agent.services.data_retention_scanner import DataRetentionScanner
from src.compliance_agent.services.remediation_integration_service import compliance_remediation_service
from src.compliance_agent.core.edgp_compliance_orchestrator import edgp_compliance_orchestrator

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.compliance_agent.models.edgp_models import DataRetentionAnalysis, ComplianceViolationRecord
from src.compliance_agent.models.compliance_models import ComplianceFramework, RiskLevel
from src.compliance_agent.services.data_retention_scanner import DataRetentionScanner
from src.compliance_agent.services.remediation_integration_service import compliance_remediation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance/edgp", tags=["EDGP Compliance"])


# Request/Response Models
class ComplianceScanRequest(BaseModel):
    """Request model for compliance scanning"""
    
    tables: Optional[List[str]] = None
    compliance_framework: ComplianceFramework = ComplianceFramework.GDPR_EU
    auto_remediate: bool = False
    risk_threshold: Optional[RiskLevel] = None


class ComplianceScanResponse(BaseModel):
    """Response model for compliance scanning"""
    
    scan_id: str
    status: str
    message: str
    analysis: Optional[DataRetentionAnalysis] = None
    remediation_summary: Optional[Dict[str, Any]] = None


class RemediationExecutionRequest(BaseModel):
    """Request model for executing remediations"""
    
    violation_ids: List[str]
    auto_execute: bool = False
    confirmation: bool = False


# Initialize scanner
scanner = DataRetentionScanner()


@router.post("/scan/data-retention", response_model=ComplianceScanResponse)
async def scan_data_retention(  # pragma: no cover
    request: ComplianceScanRequest,
    background_tasks: BackgroundTasks
):
    """
    Scan EDGP master data tables for data retention compliance violations
    """
    try:
        logger.info(f"Starting data retention compliance scan")
        
        # Validate tables
        valid_tables = ["customer", "location", "vendor", "product"]
        if request.tables:
            invalid_tables = [t for t in request.tables if t not in valid_tables]
            if invalid_tables:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid table names: {invalid_tables}. Valid tables: {valid_tables}"
                )
        
        # Perform the scan
        analysis = await scanner.scan_all_tables(
            tables=request.tables,
            compliance_framework=request.compliance_framework
        )
        
        response = ComplianceScanResponse(
            scan_id=analysis.scan_id,
            status="completed",
            message=f"Scan completed. Found {analysis.total_violations} violations.",
            analysis=analysis
        )
        
        # If auto-remediation is requested, trigger it in background
        if request.auto_remediate and analysis.violations:
            # Filter violations by risk threshold if specified
            violations_to_remediate = analysis.violations
            if request.risk_threshold:
                risk_levels = {
                    RiskLevel.LOW: [RiskLevel.LOW],
                    RiskLevel.MEDIUM: [RiskLevel.LOW, RiskLevel.MEDIUM],
                    RiskLevel.HIGH: [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH],
                    RiskLevel.CRITICAL: [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
                }
                allowed_risks = risk_levels.get(request.risk_threshold, [])
                violations_to_remediate = [
                    v for v in analysis.violations 
                    if v.risk_level in allowed_risks
                ]
            
            background_tasks.add_task(
                _background_remediation,
                violations_to_remediate,
                request.auto_remediate
            )
            
            response.message += f" Auto-remediation initiated for {len(violations_to_remediate)} violations."
        
        return response
        
    except Exception as e:
        logger.error(f"Error during compliance scan: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Compliance scan failed: {str(e)}"
        )


@router.get("/scan/{scan_id}/results", response_model=DataRetentionAnalysis)
async def get_scan_results(  # pragma: no cover
    scan_id: str = Path(..., description="Scan ID to retrieve results for")
):
    """
    Retrieve results for a specific compliance scan
    """
    # In a real implementation, this would retrieve from a database
    # For now, return an error as we don't have persistent storage
    raise HTTPException(
        status_code=404,
        detail="Scan result storage not implemented. Use the scan endpoint directly."
    )


@router.post("/remediate/violations")
async def execute_remediation(  # pragma: no cover
    request: RemediationExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute remediation workflows for specific compliance violations
    """
    try:
        if not request.confirmation:
            raise HTTPException(
                status_code=400,
                detail="Remediation execution requires explicit confirmation"
            )
        
        # This would typically retrieve violations from storage
        # For now, return an error
        raise HTTPException(
            status_code=501,
            detail="Direct violation remediation not implemented. Use scan endpoint with auto_remediate=true"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing remediation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Remediation execution failed: {str(e)}"
        )


@router.get("/tables/retention-status")
async def get_table_retention_status():  # pragma: no cover
    """
    Get data retention status overview for all EDGP master data tables
    """
    try:
        # Quick scan to get overview
        analysis = await scanner.scan_all_tables()
        
        table_status = {}
        for table_name in analysis.tables_scanned:
            table_violations = [v for v in analysis.violations if v.table_name == table_name]
            
            table_status[table_name] = {
                "total_violations": len(table_violations),
                "violations_by_risk": {
                    "critical": len([v for v in table_violations if v.risk_level == RiskLevel.CRITICAL]),
                    "high": len([v for v in table_violations if v.risk_level == RiskLevel.HIGH]),
                    "medium": len([v for v in table_violations if v.risk_level == RiskLevel.MEDIUM]),
                    "low": len([v for v in table_violations if v.risk_level == RiskLevel.LOW])
                },
                "last_scanned": analysis.scan_timestamp.isoformat()
            }
        
        return {
            "scan_id": analysis.scan_id,
            "overall_compliance_score": analysis.overall_compliance_score,
            "total_violations": analysis.total_violations,
            "table_status": table_status,
            "scan_timestamp": analysis.scan_timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting table retention status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get retention status: {str(e)}"
        )


@router.get("/violations/summary")
async def get_violations_summary(  # pragma: no cover
    table_name: Optional[str] = Query(None, description="Filter by specific table"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of violations to return")
):
    """
    Get a summary of current compliance violations
    """
    try:
        # Perform scan
        analysis = await scanner.scan_all_tables()
        
        # Filter violations
        violations = analysis.violations
        
        if table_name:
            violations = [v for v in violations if v.table_name == table_name]
        
        if risk_level:
            violations = [v for v in violations if v.risk_level == risk_level]
        
        # Limit results
        violations = violations[:limit]
        
        # Create summary
        summary = {
            "total_violations": len(violations),
            "scan_id": analysis.scan_id,
            "scan_timestamp": analysis.scan_timestamp.isoformat(),
            "filters_applied": {
                "table_name": table_name,
                "risk_level": risk_level.value if risk_level else None,
                "limit": limit
            },
            "violations": [
                {
                    "table_name": v.table_name,
                    "record_id": v.record_id,
                    "record_code": v.record_code,
                    "retention_status": v.retention_status.value,
                    "risk_level": v.risk_level.value,
                    "days_overdue": v.days_overdue,
                    "remediation_required": v.remediation_required,
                    "detected_at": v.detected_at.isoformat()
                }
                for v in violations
            ]
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting violations summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get violations summary: {str(e)}"
        )


@router.post("/remediation/status/bulk")
async def check_bulk_remediation_status(  # pragma: no cover
    remediation_ids: List[str]
):
    """
    Check the status of multiple remediation workflows
    """
    try:
        status_results = []
        
        for remediation_id in remediation_ids:
            status = await compliance_remediation_service.check_remediation_status(remediation_id)
            status_results.append({
                "remediation_id": remediation_id,
                "status": status
            })
        
        return {
            "total_checked": len(remediation_ids),
            "results": status_results,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking bulk remediation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check remediation status: {str(e)}"
        )


@router.post("/test/database-connection")
async def test_database_connection():  # pragma: no cover
    """
    Test connection to EDGP master data database
    """
    try:
        from src.compliance_agent.services.edgp_database_service_simple import EDGPDatabaseService
        edgp_db_service = EDGPDatabaseService()
        
        await edgp_db_service.initialize()
        
        # Try to get a small sample of data
        customers = await edgp_db_service.get_customers(limit=1)
        
        await edgp_db_service.close()
        
        return {
            "success": True,
            "message": "Database connection successful",
            "sample_data_available": len(customers) > 0,
            "tested_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Database connection failed: {str(e)}",
                "tested_at": datetime.utcnow().isoformat()
            }
        )


# Background task functions
async def _background_remediation(  # pragma: no cover
    violations: List[ComplianceViolationRecord],
    auto_execute: bool = False
):
    """Background task for processing remediation"""
    try:
        logger.info(f"Starting background remediation for {len(violations)} violations")
        
        result = await compliance_remediation_service.process_compliance_violations(
            violations=violations,
            auto_execute=auto_execute
        )
        
        logger.info(f"Background remediation completed: {result}")
        
    except Exception as e:
        logger.error(f"Background remediation failed: {str(e)}")
