"""
Data Governance API router
Handles data governance, breach management, and governance-related endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ...models.compliance_models import (
    DataBreachIncident,
    DataType,
    RiskLevel,
    ComplianceFramework
)
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class BreachReportRequest(BaseModel):
    """Request model for reporting a data breach"""
    severity: RiskLevel
    affected_subjects_count: int
    data_types_affected: List[DataType]
    breach_date: datetime
    discovered_date: datetime
    description: str
    cause: str
    impact_assessment: str
    containment_measures: List[str]


class BreachReportResponse(BaseModel):
    """Response model for breach reporting"""
    incident: DataBreachIncident
    notification_requirements: dict
    next_steps: List[str]


class GovernanceMetricsResponse(BaseModel):
    """Response model for governance metrics"""
    metrics: dict
    recommendations: List[str]


@router.post("/breach/report", response_model=BreachReportResponse)
async def report_data_breach(request: BreachReportRequest):
    """
    Report a data breach incident
    """
    try:
        logger.info(f"Data breach reported: {request.severity} severity, {request.affected_subjects_count} subjects affected")
        
        # Create breach incident
        incident = DataBreachIncident(
            id=f"breach_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            severity=request.severity,
            affected_subjects_count=request.affected_subjects_count,
            data_types_affected=request.data_types_affected,
            breach_date=request.breach_date,
            discovered_date=request.discovered_date,
            description=request.description,
            cause=request.cause,
            impact_assessment=request.impact_assessment,
            containment_measures=request.containment_measures,
            notification_required=_determine_dpa_notification_required(request),
            subject_notification_required=_determine_subject_notification_required(request)
        )
        
        # Determine notification requirements
        notification_requirements = _get_notification_requirements(incident)
        
        # Generate next steps
        next_steps = _generate_breach_response_steps(incident)
        
        return BreachReportResponse(
            incident=incident,
            notification_requirements=notification_requirements,
            next_steps=next_steps
        )
        
    except Exception as e:
        logger.error(f"Error reporting data breach: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Breach reporting failed: {str(e)}"
        )


@router.get("/breach/{incident_id}")
async def get_breach_incident(incident_id: str):
    """
    Get details of a specific breach incident
    """
    try:
        # In a real implementation, this would query a database
        return {
            "incident_id": incident_id,
            "message": "This would return actual breach incident details from database"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving breach incident: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve breach incident: {str(e)}"
        )


@router.get("/metrics", response_model=GovernanceMetricsResponse)
async def get_governance_metrics():
    """
    Get data governance metrics and KPIs
    """
    try:
        # In a real implementation, this would calculate actual metrics from data
        metrics = {
            "compliance_score": 85.2,
            "total_assessments": 42,
            "compliant_activities": 35,
            "non_compliant_activities": 7,
            "high_risk_activities": 3,
            "data_breaches_ytd": 1,
            "privacy_requests_ytd": 156,
            "consent_rate": 92.4,
            "data_retention_compliance": 88.1
        }
        
        recommendations = [
            "Address 7 non-compliant data processing activities",
            "Implement additional controls for 3 high-risk activities", 
            "Improve data retention policy compliance",
            "Conduct privacy training for data processing teams",
            "Review and update consent mechanisms"
        ]
        
        return GovernanceMetricsResponse(
            metrics=metrics,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error retrieving governance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve governance metrics: {str(e)}"
        )


@router.get("/frameworks/singapore")
async def get_singapore_frameworks():
    """
    Get information about Singapore-specific data protection frameworks
    """
    return {
        "frameworks": [
            {
                "name": "Personal Data Protection Act (PDPA)",
                "description": "Singapore's primary data protection law",
                "key_requirements": [
                    "Consent for collection, use and disclosure",
                    "Purpose limitation",
                    "Notification and access obligations",
                    "Data protection and retention obligations",
                    "Data breach notification requirements"
                ],
                "penalties": "Up to S$1 million in financial penalties",
                "dpa": "Personal Data Protection Commission (PDPC)"
            },
            {
                "name": "Cybersecurity Act",
                "description": "Framework for cybersecurity in Singapore",
                "key_requirements": [
                    "Cybersecurity incident reporting",
                    "Critical information infrastructure protection",
                    "Cybersecurity codes of practice"
                ]
            },
            {
                "name": "Banking Act",
                "description": "Specific requirements for financial institutions",
                "key_requirements": [
                    "Customer data protection",
                    "Outsourcing risk management",
                    "Technology risk management"
                ]
            }
        ]
    }


@router.get("/best-practices")
async def get_best_practices():
    """
    Get data governance best practices
    """
    return {
        "best_practices": [
            {
                "category": "Data Classification",
                "practices": [
                    "Implement data classification scheme",
                    "Label data based on sensitivity levels",
                    "Apply appropriate controls based on classification"
                ]
            },
            {
                "category": "Access Control",
                "practices": [
                    "Implement role-based access control",
                    "Regular access reviews and certifications",
                    "Principle of least privilege",
                    "Multi-factor authentication for sensitive data"
                ]
            },
            {
                "category": "Data Lifecycle Management",
                "practices": [
                    "Define data retention policies",
                    "Implement automated data deletion",
                    "Regular data quality assessments",
                    "Secure data disposal procedures"
                ]
            },
            {
                "category": "Privacy by Design",
                "practices": [
                    "Build privacy into system design",
                    "Conduct privacy impact assessments",
                    "Implement data minimization",
                    "Ensure transparency and user control"
                ]
            },
            {
                "category": "Incident Response",
                "practices": [
                    "Develop incident response procedures",
                    "Regular incident response testing",
                    "Clear escalation procedures",
                    "Documentation and lessons learned"
                ]
            }
        ]
    }


def _determine_dpa_notification_required(request: BreachReportRequest) -> bool:
    """Determine if DPA notification is required"""
    # PDPA Singapore: Notify if affects 500+ individuals
    # GDPR: Notify within 72 hours if likely to result in risk
    if request.affected_subjects_count >= 500:
        return True
    if request.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        return True
    return False


def _determine_subject_notification_required(request: BreachReportRequest) -> bool:
    """Determine if data subject notification is required"""
    # Required if likely to cause significant harm
    return request.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]


def _get_notification_requirements(incident: DataBreachIncident) -> dict:
    """Get notification requirements based on incident details"""
    requirements = {
        "dpa_notification": {
            "required": incident.notification_required,
            "timeframe": "72 hours (GDPR) or immediately if 500+ subjects (PDPA)",
            "authorities": ["PDPC (Singapore)", "Relevant EU DPA (if GDPR applies)"]
        },
        "subject_notification": {
            "required": incident.subject_notification_required,
            "timeframe": "Without undue delay",
            "method": "Direct communication where feasible"
        }
    }
    return requirements


def _generate_breach_response_steps(incident: DataBreachIncident) -> List[str]:
    """Generate next steps for breach response"""
    steps = [
        "Document the incident thoroughly",
        "Assess the scope and impact of the breach",
        "Implement immediate containment measures"
    ]
    
    if incident.notification_required:
        steps.append("Prepare and submit notification to data protection authority")
    
    if incident.subject_notification_required:
        steps.append("Notify affected data subjects")
    
    steps.extend([
        "Conduct forensic investigation if required",
        "Review and update security measures",
        "Provide training to prevent similar incidents",
        "Monitor for any ongoing risks"
    ])
    
    return steps