"""
Core models for the AI Compliance Agent
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks"""
    PDPA_SINGAPORE = "pdpa_singapore"
    GDPR_EU = "gdpr_eu"
    CCPA_CALIFORNIA = "ccpa_california"
    PIPEDA_CANADA = "pipeda_canada"
    LGPD_BRAZIL = "lgpd_brazil"
    ISO_27001 = "iso_27001"
    SOC2 = "soc2"


class DataType(str, Enum):
    """Types of data that can be processed"""
    PERSONAL_DATA = "personal_data"
    SENSITIVE_DATA = "sensitive_data"
    FINANCIAL_DATA = "financial_data"
    HEALTH_DATA = "health_data"
    BIOMETRIC_DATA = "biometric_data"
    LOCATION_DATA = "location_data"
    BEHAVIORAL_DATA = "behavioral_data"


class RiskLevel(str, Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(str, Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REQUIRES_REVIEW = "requires_review"
    UNKNOWN = "unknown"


class DataSubject(BaseModel):
    """Model representing a data subject"""
    id: str = Field(..., description="Unique identifier for the data subject")
    region: str = Field(..., description="Geographic region of the data subject")
    consent_status: bool = Field(default=False, description="Current consent status")
    consent_timestamp: Optional[datetime] = Field(None, description="When consent was given")
    data_types: List[DataType] = Field(default_factory=list, description="Types of data collected")


class DataProcessingActivity(BaseModel):
    """Model representing a data processing activity"""
    id: str = Field(..., description="Unique identifier for the processing activity")
    name: str = Field(..., description="Name of the processing activity")
    purpose: str = Field(..., description="Purpose of data processing")
    data_types: List[DataType] = Field(..., description="Types of data being processed")
    legal_bases: List[str] = Field(..., description="Legal bases for processing")
    retention_period: Optional[int] = Field(None, description="Data retention period in days")
    recipients: List[str] = Field(default_factory=list, description="Data recipients")
    cross_border_transfers: bool = Field(default=False, description="Whether data crosses borders")
    automated_decision_making: bool = Field(default=False, description="Whether automated decisions are made")


class ComplianceRule(BaseModel):
    """Model representing a compliance rule"""
    id: str = Field(..., description="Unique identifier for the rule")
    framework: ComplianceFramework = Field(..., description="Compliance framework")
    article: str = Field(..., description="Article or section reference")
    title: str = Field(..., description="Rule title")
    description: str = Field(..., description="Rule description")
    requirements: List[str] = Field(..., description="Specific requirements")
    applicable_data_types: List[DataType] = Field(..., description="Applicable data types")
    severity: RiskLevel = Field(..., description="Severity of non-compliance")


class ComplianceViolation(BaseModel):
    """Model representing a compliance violation"""
    rule_id: str = Field(..., description="ID of the violated rule")
    activity_id: str = Field(..., description="ID of the processing activity")
    description: str = Field(..., description="Description of the violation")
    risk_level: RiskLevel = Field(..., description="Risk level of the violation")
    remediation_actions: List[str] = Field(..., description="Suggested remediation actions")
    detected_at: datetime = Field(default_factory=datetime.utcnow, description="When violation was detected")


class ComplianceAssessment(BaseModel):
    """Model representing a compliance assessment result"""
    id: str = Field(..., description="Unique identifier for the assessment")
    framework: ComplianceFramework = Field(..., description="Framework used for assessment")
    activity: DataProcessingActivity = Field(..., description="Assessed processing activity")
    status: ComplianceStatus = Field(..., description="Overall compliance status")
    score: float = Field(..., ge=0, le=100, description="Compliance score (0-100)")
    violations: List[ComplianceViolation] = Field(default_factory=list, description="Identified violations")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    assessed_at: datetime = Field(default_factory=datetime.utcnow, description="Assessment timestamp")
    assessor: str = Field(..., description="Who/what performed the assessment")


class PrivacyImpactAssessment(BaseModel):
    """Model for Privacy Impact Assessment (PIA/DPIA)"""
    id: str = Field(..., description="Unique identifier for the PIA")
    project_name: str = Field(..., description="Name of the project being assessed")
    description: str = Field(..., description="Description of the project")
    data_types: List[DataType] = Field(..., description="Types of data involved")
    processing_activities: List[DataProcessingActivity] = Field(..., description="Processing activities")
    risk_assessment: Dict[str, Any] = Field(..., description="Detailed risk assessment")
    mitigation_measures: List[str] = Field(..., description="Risk mitigation measures")
    overall_risk: RiskLevel = Field(..., description="Overall risk level")
    requires_consultation: bool = Field(default=False, description="Whether DPA consultation is required")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class ConsentRecord(BaseModel):
    """Model for consent management"""
    id: str = Field(..., description="Unique identifier for the consent record")
    subject_id: str = Field(..., description="Data subject identifier")
    purpose: str = Field(..., description="Purpose for which consent was given")
    data_types: List[DataType] = Field(..., description="Data types covered by consent")
    consent_given: bool = Field(..., description="Whether consent was given")
    consent_timestamp: datetime = Field(..., description="When consent was given/withdrawn")
    consent_method: str = Field(..., description="How consent was obtained")
    withdrawal_timestamp: Optional[datetime] = Field(None, description="When consent was withdrawn")
    legal_basis: str = Field(..., description="Legal basis for processing")
    expiry_date: Optional[datetime] = Field(None, description="When consent expires")


class DataBreachIncident(BaseModel):
    """Model for data breach incident tracking"""
    id: str = Field(..., description="Unique identifier for the breach")
    severity: RiskLevel = Field(..., description="Severity of the breach")
    affected_subjects_count: int = Field(..., ge=0, description="Number of affected data subjects")
    data_types_affected: List[DataType] = Field(..., description="Types of data affected")
    breach_date: datetime = Field(..., description="When the breach occurred")
    discovered_date: datetime = Field(..., description="When the breach was discovered")
    reported_date: Optional[datetime] = Field(None, description="When the breach was reported to authorities")
    description: str = Field(..., description="Description of the breach")
    cause: str = Field(..., description="Cause of the breach")
    impact_assessment: str = Field(..., description="Assessment of the impact")
    containment_measures: List[str] = Field(..., description="Measures taken to contain the breach")
    notification_required: bool = Field(..., description="Whether notification to DPA is required")
    subject_notification_required: bool = Field(..., description="Whether subjects need to be notified")