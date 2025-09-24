"""
Compliance API router
Handles compliance checking endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from pydantic import BaseModel

from ...core.compliance_engine import ComplianceEngine
from ...models.compliance_models import (
    ComplianceFramework,
    DataProcessingActivity,
    ComplianceAssessment,
    DataType,
    RiskLevel
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ComplianceCheckRequest(BaseModel):
    """Request model for compliance checking"""
    activity: DataProcessingActivity
    frameworks: List[ComplianceFramework]
    include_ai_analysis: bool = True


class ComplianceCheckResponse(BaseModel):
    """Response model for compliance checking"""
    assessments: List[ComplianceAssessment]
    overall_status: str
    summary: dict


# Dependency to get compliance engine (to be injected from main app)
async def get_compliance_engine() -> ComplianceEngine:
    """This will be overridden by the main app dependency"""
    pass


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    request: ComplianceCheckRequest,
    engine: ComplianceEngine = Depends(get_compliance_engine)
):
    """
    Check compliance of a data processing activity against specified frameworks
    """
    try:
        logger.info(f"Compliance check requested for activity {request.activity.id}")
        
        assessments = await engine.assess_compliance(
            activity=request.activity,
            frameworks=request.frameworks,
            include_ai_analysis=request.include_ai_analysis
        )
        
        # Calculate overall status
        overall_status = "compliant"
        if any(a.status.value == "non_compliant" for a in assessments):
            overall_status = "non_compliant"
        elif any(a.status.value == "requires_review" for a in assessments):
            overall_status = "requires_review"
        
        # Create summary
        summary = {
            "total_assessments": len(assessments),
            "compliant_count": sum(1 for a in assessments if a.status.value == "compliant"),
            "non_compliant_count": sum(1 for a in assessments if a.status.value == "non_compliant"),
            "requires_review_count": sum(1 for a in assessments if a.status.value == "requires_review"),
            "average_score": sum(a.score for a in assessments) / len(assessments) if assessments else 0,
            "total_violations": sum(len(a.violations) for a in assessments)
        }
        
        return ComplianceCheckResponse(
            assessments=assessments,
            overall_status=overall_status,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error during compliance check: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(e)}"
        )


@router.get("/frameworks")
async def get_supported_frameworks():
    """Get list of supported compliance frameworks"""
    return {
        "frameworks": [
            {
                "code": framework.value,
                "name": framework.name,
                "description": _get_framework_description(framework)
            }
            for framework in ComplianceFramework
        ]
    }


@router.get("/data-types")
async def get_supported_data_types():
    """Get list of supported data types"""
    return {
        "data_types": [
            {
                "code": data_type.value,
                "name": data_type.name,
                "description": _get_data_type_description(data_type)
            }
            for data_type in DataType
        ]
    }


@router.get("/risk-levels")
async def get_risk_levels():
    """Get list of risk levels"""
    return {
        "risk_levels": [
            {
                "code": risk_level.value,
                "name": risk_level.name,
                "description": _get_risk_level_description(risk_level)
            }
            for risk_level in RiskLevel
        ]
    }


def _get_framework_description(framework: ComplianceFramework) -> str:
    """Get description for a compliance framework"""
    descriptions = {
        ComplianceFramework.PDPA_SINGAPORE: "Singapore Personal Data Protection Act",
        ComplianceFramework.GDPR_EU: "European Union General Data Protection Regulation",
        ComplianceFramework.CCPA_CALIFORNIA: "California Consumer Privacy Act",
        ComplianceFramework.PIPEDA_CANADA: "Personal Information Protection and Electronic Documents Act (Canada)",
        ComplianceFramework.LGPD_BRAZIL: "Brazilian General Data Protection Law",
        ComplianceFramework.ISO_27001: "ISO/IEC 27001 Information Security Management",
        ComplianceFramework.SOC2: "SOC 2 Service Organization Control 2"
    }
    return descriptions.get(framework, "Unknown framework")


def _get_data_type_description(data_type: DataType) -> str:
    """Get description for a data type"""
    descriptions = {
        DataType.PERSONAL_DATA: "Any information relating to an identified or identifiable natural person",
        DataType.SENSITIVE_DATA: "Special categories of personal data requiring enhanced protection",
        DataType.FINANCIAL_DATA: "Financial information and payment data",
        DataType.HEALTH_DATA: "Health and medical information",
        DataType.BIOMETRIC_DATA: "Biometric identifiers such as fingerprints, facial recognition",
        DataType.LOCATION_DATA: "Geographic location information",
        DataType.BEHAVIORAL_DATA: "Information about behavior, preferences, and interactions"
    }
    return descriptions.get(data_type, "Unknown data type")


def _get_risk_level_description(risk_level: RiskLevel) -> str:
    """Get description for a risk level"""
    descriptions = {
        RiskLevel.LOW: "Low risk - minimal impact on data subjects",
        RiskLevel.MEDIUM: "Medium risk - moderate impact requiring attention",
        RiskLevel.HIGH: "High risk - significant impact requiring immediate action",
        RiskLevel.CRITICAL: "Critical risk - severe impact requiring urgent remediation"
    }
    return descriptions.get(risk_level, "Unknown risk level")