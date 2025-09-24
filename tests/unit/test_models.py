"""
Unit tests for compliance models
"""

import pytest
from datetime import datetime
from typing import List

from src.compliance_agent.models.compliance_models import (
    ComplianceFramework,
    DataType,
    RiskLevel,
    ComplianceStatus,
    DataSubject,
    DataProcessingActivity,
    ComplianceRule,
    ComplianceViolation,
    ComplianceAssessment,
    PrivacyImpactAssessment,
    ConsentRecord,
    DataBreachIncident
)


class TestComplianceModels:
    """Test compliance model classes"""
    
    def test_data_subject_creation(self):
        """Test DataSubject model creation"""
        subject = DataSubject(
            id="subject_001",
            region="Singapore",
            consent_status=True,
            consent_timestamp=datetime.utcnow(),
            data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA]
        )
        
        assert subject.id == "subject_001"
        assert subject.region == "Singapore"
        assert subject.consent_status is True
        assert len(subject.data_types) == 2
        assert DataType.PERSONAL_DATA in subject.data_types
    
    def test_data_processing_activity_creation(self):
        """Test DataProcessingActivity model creation"""
        activity = DataProcessingActivity(
            id="activity_001",
            name="Customer Registration",
            purpose="Collect customer information for account creation",
            data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
            legal_bases=["consent", "contract"],
            retention_period=2555,  # 7 years in days
            recipients=["internal_team", "payment_processor"],
            cross_border_transfers=False,
            automated_decision_making=False
        )
        
        assert activity.id == "activity_001"
        assert activity.name == "Customer Registration"
        assert len(activity.data_types) == 2
        assert len(activity.legal_bases) == 2
        assert activity.retention_period == 2555
        assert not activity.cross_border_transfers
    
    def test_compliance_rule_creation(self):
        """Test ComplianceRule model creation"""
        rule = ComplianceRule(
            id="pdpa_consent_001",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            article="Section 13",
            title="Consent for Collection",
            description="Personal data must not be collected without consent",
            requirements=["Obtain consent", "Informed consent", "Withdrawable consent"],
            applicable_data_types=[DataType.PERSONAL_DATA],
            severity=RiskLevel.HIGH
        )
        
        assert rule.id == "pdpa_consent_001"
        assert rule.framework == ComplianceFramework.PDPA_SINGAPORE
        assert rule.severity == RiskLevel.HIGH
        assert len(rule.requirements) == 3
    
    def test_compliance_violation_creation(self):
        """Test ComplianceViolation model creation"""
        violation = ComplianceViolation(
            rule_id="pdpa_consent_001",
            activity_id="activity_001",
            description="No consent mechanism implemented",
            risk_level=RiskLevel.HIGH,
            remediation_actions=["Implement consent form", "Update privacy policy"]
        )
        
        assert violation.rule_id == "pdpa_consent_001"
        assert violation.activity_id == "activity_001"
        assert violation.risk_level == RiskLevel.HIGH
        assert len(violation.remediation_actions) == 2
        assert isinstance(violation.detected_at, datetime)
    
    def test_compliance_assessment_creation(self):
        """Test ComplianceAssessment model creation"""
        activity = DataProcessingActivity(
            id="activity_001",
            name="Test Activity",
            purpose="Testing",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            recipients=[]
        )
        
        assessment = ComplianceAssessment(
            id="assessment_001",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=activity,
            status=ComplianceStatus.COMPLIANT,
            score=95.5,
            violations=[],
            recommendations=["Continue good practices"],
            assessor="ai_compliance_engine"
        )
        
        assert assessment.id == "assessment_001"
        assert assessment.framework == ComplianceFramework.PDPA_SINGAPORE
        assert assessment.status == ComplianceStatus.COMPLIANT
        assert assessment.score == 95.5
        assert len(assessment.violations) == 0
        assert isinstance(assessment.assessed_at, datetime)
    
    def test_privacy_impact_assessment_creation(self):
        """Test PrivacyImpactAssessment model creation"""
        activity = DataProcessingActivity(
            id="activity_001",
            name="Test Activity",
            purpose="Testing",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            recipients=[]
        )
        
        pia = PrivacyImpactAssessment(
            id="pia_001",
            project_name="Customer Portal",
            description="New customer portal implementation",
            data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
            processing_activities=[activity],
            risk_assessment={"activity_001": 25.5},
            mitigation_measures=["Implement encryption", "Access controls"],
            overall_risk=RiskLevel.MEDIUM,
            requires_consultation=False
        )
        
        assert pia.id == "pia_001"
        assert pia.project_name == "Customer Portal"
        assert pia.overall_risk == RiskLevel.MEDIUM
        assert not pia.requires_consultation
        assert len(pia.processing_activities) == 1
    
    def test_consent_record_creation(self):
        """Test ConsentRecord model creation"""
        consent = ConsentRecord(
            id="consent_001",
            subject_id="subject_001",
            purpose="Marketing communications",
            data_types=[DataType.PERSONAL_DATA],
            consent_given=True,
            consent_timestamp=datetime.utcnow(),
            consent_method="web_form",
            legal_basis="consent"
        )
        
        assert consent.id == "consent_001"
        assert consent.subject_id == "subject_001"
        assert consent.consent_given is True
        assert consent.consent_method == "web_form"
        assert isinstance(consent.consent_timestamp, datetime)
    
    def test_data_breach_incident_creation(self):
        """Test DataBreachIncident model creation"""
        breach = DataBreachIncident(
            id="breach_001",
            severity=RiskLevel.HIGH,
            affected_subjects_count=1500,
            data_types_affected=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
            breach_date=datetime.utcnow(),
            discovered_date=datetime.utcnow(),
            description="Unauthorized access to customer database",
            cause="SQL injection attack",
            impact_assessment="High impact due to financial data exposure",
            containment_measures=["Patched vulnerability", "Reset passwords"],
            notification_required=True,
            subject_notification_required=True
        )
        
        assert breach.id == "breach_001"
        assert breach.severity == RiskLevel.HIGH
        assert breach.affected_subjects_count == 1500
        assert len(breach.data_types_affected) == 2
        assert breach.notification_required is True
        assert breach.subject_notification_required is True


class TestModelValidation:
    """Test model validation and constraints"""
    
    def test_compliance_assessment_score_validation(self):
        """Test that compliance assessment score is validated"""
        activity = DataProcessingActivity(
            id="activity_001",
            name="Test Activity",
            purpose="Testing",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            recipients=[]
        )
        
        # Valid score
        assessment = ComplianceAssessment(
            id="assessment_001",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=activity,
            status=ComplianceStatus.COMPLIANT,
            score=85.5,
            assessor="test"
        )
        assert assessment.score == 85.5
        
        # Test score boundaries
        assessment_min = ComplianceAssessment(
            id="assessment_002",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=activity,
            status=ComplianceStatus.COMPLIANT,
            score=0.0,
            assessor="test"
        )
        assert assessment_min.score == 0.0
        
        assessment_max = ComplianceAssessment(
            id="assessment_003",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=activity,
            status=ComplianceStatus.COMPLIANT,
            score=100.0,
            assessor="test"
        )
        assert assessment_max.score == 100.0
    
    def test_data_breach_affected_count_validation(self):
        """Test that data breach affected count is validated"""
        breach = DataBreachIncident(
            id="breach_001",
            severity=RiskLevel.MEDIUM,
            affected_subjects_count=0,
            data_types_affected=[DataType.PERSONAL_DATA],
            breach_date=datetime.utcnow(),
            discovered_date=datetime.utcnow(),
            description="Test breach",
            cause="Test cause",
            impact_assessment="Test impact",
            containment_measures=["Test measure"],
            notification_required=False,
            subject_notification_required=False
        )
        assert breach.affected_subjects_count == 0


if __name__ == "__main__":
    pytest.main([__file__])