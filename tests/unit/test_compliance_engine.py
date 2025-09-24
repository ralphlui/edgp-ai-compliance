"""
Unit tests for the compliance engine
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.compliance_agent.core.compliance_engine import ComplianceEngine
from src.compliance_agent.models.compliance_models import (
    ComplianceFramework,
    DataType,
    RiskLevel,
    ComplianceStatus,
    DataProcessingActivity,
    ComplianceAssessment,
    PrivacyImpactAssessment
)


class TestComplianceEngine:
    """Test the main compliance engine functionality"""
    
    @pytest.fixture
    async def engine(self):
        """Create a compliance engine instance for testing"""
        engine = ComplianceEngine()
        # Mock the initialization to avoid external dependencies
        with patch.object(engine.rule_engine, 'load_rules', new_callable=AsyncMock):
            with patch.object(engine.ai_analyzer, 'initialize', new_callable=AsyncMock):
                await engine.initialize()
        return engine
    
    @pytest.fixture
    def sample_activity(self):
        """Create a sample data processing activity for testing"""
        return DataProcessingActivity(
            id="test_activity_001",
            name="Customer Registration",
            purpose="Collect customer information for account creation and service delivery",
            data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
            legal_bases=["consent", "contract"],
            retention_period=2555,  # 7 years
            recipients=["internal_sales", "payment_processor"],
            cross_border_transfers=False,
            automated_decision_making=False
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test compliance engine initialization"""
        engine = ComplianceEngine()
        
        with patch.object(engine.rule_engine, 'load_rules', new_callable=AsyncMock) as mock_load_rules:
            with patch.object(engine.ai_analyzer, 'initialize', new_callable=AsyncMock) as mock_ai_init:
                await engine.initialize()
                
                mock_load_rules.assert_called_once()
                mock_ai_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_assess_compliance_single_framework(self, engine, sample_activity):
        """Test compliance assessment for a single framework"""
        frameworks = [ComplianceFramework.PDPA_SINGAPORE]
        
        # Mock the rule engine and AI analyzer
        mock_rules = []
        mock_violations = []
        mock_ai_analysis = {'violations': [], 'recommendations': []}
        
        with patch.object(engine.rule_engine, 'get_rules_for_framework', return_value=mock_rules):
            with patch.object(engine, '_check_rule_violations', return_value=mock_violations):
                with patch.object(engine.ai_analyzer, 'analyze_activity', return_value=mock_ai_analysis):
                    
                    assessments = await engine.assess_compliance(
                        activity=sample_activity,
                        frameworks=frameworks,
                        include_ai_analysis=True
                    )
                    
                    assert len(assessments) == 1
                    assert assessments[0].framework == ComplianceFramework.PDPA_SINGAPORE
                    assert assessments[0].activity.id == sample_activity.id
                    assert isinstance(assessments[0].score, float)
                    assert 0 <= assessments[0].score <= 100
    
    @pytest.mark.asyncio
    async def test_assess_compliance_multiple_frameworks(self, engine, sample_activity):
        """Test compliance assessment for multiple frameworks"""
        frameworks = [ComplianceFramework.PDPA_SINGAPORE, ComplianceFramework.GDPR_EU]
        
        # Mock dependencies
        with patch.object(engine.rule_engine, 'get_rules_for_framework', return_value=[]):
            with patch.object(engine, '_check_rule_violations', return_value=[]):
                with patch.object(engine.ai_analyzer, 'analyze_activity', return_value={'violations': [], 'recommendations': []}):
                    
                    assessments = await engine.assess_compliance(
                        activity=sample_activity,
                        frameworks=frameworks,
                        include_ai_analysis=True
                    )
                    
                    assert len(assessments) == 2
                    framework_types = [a.framework for a in assessments]
                    assert ComplianceFramework.PDPA_SINGAPORE in framework_types
                    assert ComplianceFramework.GDPR_EU in framework_types
    
    @pytest.mark.asyncio
    async def test_assess_compliance_without_ai(self, engine, sample_activity):
        """Test compliance assessment without AI analysis"""
        frameworks = [ComplianceFramework.PDPA_SINGAPORE]
        
        with patch.object(engine.rule_engine, 'get_rules_for_framework', return_value=[]):
            with patch.object(engine, '_check_rule_violations', return_value=[]):
                # AI analyzer should not be called
                with patch.object(engine.ai_analyzer, 'analyze_activity') as mock_ai:
                    
                    assessments = await engine.assess_compliance(
                        activity=sample_activity,
                        frameworks=frameworks,
                        include_ai_analysis=False
                    )
                    
                    assert len(assessments) == 1
                    mock_ai.assert_not_called()
    
    def test_calculate_compliance_score_no_violations(self, engine):
        """Test compliance score calculation with no violations"""
        violations = []
        rules = []
        
        score = engine._calculate_compliance_score(violations, rules)
        assert score == 100.0
    
    def test_calculate_compliance_score_with_violations(self, engine):
        """Test compliance score calculation with violations"""
        from src.compliance_agent.models.compliance_models import ComplianceViolation
        
        violations = [
            ComplianceViolation(
                rule_id="test_rule_1",
                activity_id="test_activity",
                description="Test violation",
                risk_level=RiskLevel.MEDIUM,
                remediation_actions=["Fix it"]
            ),
            ComplianceViolation(
                rule_id="test_rule_2", 
                activity_id="test_activity",
                description="Another test violation",
                risk_level=RiskLevel.HIGH,
                remediation_actions=["Fix this too"]
            )
        ]
        rules = [Mock(), Mock(), Mock()]  # 3 rules
        
        score = engine._calculate_compliance_score(violations, rules)
        assert 0 <= score < 100
    
    def test_determine_compliance_status(self, engine):
        """Test compliance status determination"""
        from src.compliance_agent.models.compliance_models import ComplianceViolation
        
        # No violations = compliant
        assert engine._determine_compliance_status([]) == ComplianceStatus.COMPLIANT
        
        # Critical violation = non-compliant
        critical_violation = ComplianceViolation(
            rule_id="test",
            activity_id="test",
            description="Critical issue",
            risk_level=RiskLevel.CRITICAL,
            remediation_actions=[]
        )
        assert engine._determine_compliance_status([critical_violation]) == ComplianceStatus.NON_COMPLIANT
        
        # High violation = requires review
        high_violation = ComplianceViolation(
            rule_id="test",
            activity_id="test", 
            description="High risk issue",
            risk_level=RiskLevel.HIGH,
            remediation_actions=[]
        )
        assert engine._determine_compliance_status([high_violation]) == ComplianceStatus.REQUIRES_REVIEW
        
        # Medium violation = requires review
        medium_violation = ComplianceViolation(
            rule_id="test",
            activity_id="test",
            description="Medium risk issue", 
            risk_level=RiskLevel.MEDIUM,
            remediation_actions=[]
        )
        assert engine._determine_compliance_status([medium_violation]) == ComplianceStatus.REQUIRES_REVIEW
    
    @pytest.mark.asyncio
    async def test_conduct_privacy_impact_assessment(self, engine):
        """Test Privacy Impact Assessment functionality"""
        processing_activities = [
            DataProcessingActivity(
                id="pia_activity_001",
                name="Customer Data Processing",
                purpose="Process customer data for service delivery",
                data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
                legal_bases=["consent"],
                recipients=["internal_team"],
                cross_border_transfers=False,
                automated_decision_making=False
            )
        ]
        
        # Mock the assess_compliance method
        mock_assessment = ComplianceAssessment(
            id="mock_assessment",
            framework=ComplianceFramework.PDPA_SINGAPORE,
            activity=processing_activities[0],
            status=ComplianceStatus.COMPLIANT,
            score=85.0,
            assessor="test"
        )
        
        with patch.object(engine, 'assess_compliance', return_value=[mock_assessment]):
            pia = await engine.conduct_privacy_impact_assessment(
                project_name="Test Project",
                description="Test project description",
                processing_activities=processing_activities
            )
            
            assert isinstance(pia, PrivacyImpactAssessment)
            assert pia.project_name == "Test Project"
            assert pia.description == "Test project description"
            assert len(pia.processing_activities) == 1
            assert pia.overall_risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            assert isinstance(pia.requires_consultation, bool)
    
    def test_risk_score_to_level(self, engine):
        """Test risk score to level conversion"""
        assert engine._risk_score_to_level(80) == RiskLevel.CRITICAL
        assert engine._risk_score_to_level(60) == RiskLevel.HIGH
        assert engine._risk_score_to_level(40) == RiskLevel.MEDIUM
        assert engine._risk_score_to_level(10) == RiskLevel.LOW
        assert engine._risk_score_to_level(0) == RiskLevel.LOW
    
    def test_generate_mitigation_measures(self, engine):
        """Test mitigation measures generation"""
        activities = [
            DataProcessingActivity(
                id="test_activity",
                name="Test",
                purpose="Test purpose",
                data_types=[DataType.PERSONAL_DATA],
                legal_bases=["consent"],
                recipients=[],
                cross_border_transfers=True,
                automated_decision_making=True
            )
        ]
        
        measures = engine._generate_mitigation_measures(activities, RiskLevel.HIGH)
        
        assert isinstance(measures, list)
        assert len(measures) > 0
        # Should include base measures
        assert any("data minimization" in measure.lower() for measure in measures)
        # Should include high-risk specific measures
        assert any("privacy by design" in measure.lower() for measure in measures)
        # Should include activity-specific measures
        assert any("international" in measure.lower() or "transfer" in measure.lower() for measure in measures)
        assert any("automated" in measure.lower() for measure in measures)


class TestComplianceEngineErrorHandling:
    """Test error handling in compliance engine"""
    
    @pytest.mark.asyncio
    async def test_assess_compliance_with_error(self):
        """Test compliance assessment error handling"""
        engine = ComplianceEngine()
        
        activity = DataProcessingActivity(
            id="error_test",
            name="Error Test",
            purpose="Test error handling",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            recipients=[]
        )
        
        frameworks = [ComplianceFramework.PDPA_SINGAPORE]
        
        # Mock rule engine to raise an exception
        with patch.object(engine.rule_engine, 'get_rules_for_framework', side_effect=Exception("Test error")):
            assessments = await engine.assess_compliance(
                activity=activity,
                frameworks=frameworks,
                include_ai_analysis=False
            )
            
            assert len(assessments) == 1
            assert assessments[0].status == ComplianceStatus.UNKNOWN
            assert assessments[0].score == 0.0
            assert "Assessment failed" in assessments[0].recommendations[0]


if __name__ == "__main__":
    pytest.main([__file__])