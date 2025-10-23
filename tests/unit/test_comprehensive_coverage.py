"""
Comprehensive coverage tests for maximizing code coverage
This file contains tests designed to maximize coverage across the codebase
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import List

# Test imports
from src.compliance_agent.models.compliance_models import *
from src.compliance_agent.services.rule_engine import ComplianceRuleEngine
from src.compliance_agent.services.ai_analyzer import AIComplianceAnalyzer
from src.compliance_agent.core.compliance_engine import ComplianceEngine


class TestRuleEngineComprehensive:
    """Comprehensive tests for Rule Engine"""

    @pytest.mark.asyncio
    async def test_rule_engine_initialization(self):
        """Test rule engine initialization and rule loading"""
        engine = ComplianceRuleEngine()
        await engine.load_rules()

        assert engine._rules_loaded is True
        assert len(engine.rules) >= 2

    @pytest.mark.asyncio
    async def test_get_pdpa_rules(self):
        """Test getting PDPA rules"""
        engine = ComplianceRuleEngine()
        rules = await engine.get_rules_for_framework(ComplianceFramework.PDPA_SINGAPORE)

        assert isinstance(rules, list)
        assert len(rules) > 0
        for rule in rules:
            assert rule.framework == ComplianceFramework.PDPA_SINGAPORE

    @pytest.mark.asyncio
    async def test_get_gdpr_rules(self):
        """Test getting GDPR rules"""
        engine = ComplianceRuleEngine()
        rules = await engine.get_rules_for_framework(ComplianceFramework.GDPR_EU)

        assert isinstance(rules, list)
        assert len(rules) > 0
        for rule in rules:
            assert rule.framework == ComplianceFramework.GDPR_EU


class TestAIAnalyzerComprehensive:
    """Comprehensive tests for AI Analyzer"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mocked API key"""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key-12345'}):
            return AIComplianceAnalyzer()

    @pytest.fixture
    def sample_activity(self):
        """Sample activity for testing"""
        return DataProcessingActivity(
            id="test_001",
            name="Test Activity",
            purpose="Test purpose",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            retention_period=365,
            recipients=["internal"],
            cross_border_transfers=False,
            automated_decision_making=False
        )

    def test_analyzer_creation(self, analyzer):
        """Test analyzer instantiation"""
        assert analyzer is not None


class TestComplianceEngineComprehensive:
    """Comprehensive tests for Compliance Engine"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return ComplianceEngine()

    @pytest.fixture
    def sample_activity(self):
        """Sample activity"""
        return DataProcessingActivity(
            id="engine_test_001",
            name="Engine Test Activity",
            purpose="Testing the engine",
            data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA],
            legal_bases=["consent", "contract"],
            retention_period=730,
            recipients=["internal_team"],
            cross_border_transfers=False,
            automated_decision_making=False
        )

    def test_engine_initialization(self, engine):
        """Test engine instantiation"""
        assert engine is not None
        assert engine.rule_engine is not None
        assert engine.ai_analyzer is not None

    @pytest.mark.asyncio
    async def test_engine_initialize(self, engine):
        """Test engine initialization"""
        with patch.object(engine.rule_engine, 'load_rules', new_callable=AsyncMock):
            with patch.object(engine.ai_analyzer, 'initialize', new_callable=AsyncMock):
                await engine.initialize()

    def test_risk_level_conversion(self, engine):
        """Test risk score to level conversion"""
        assert engine._risk_score_to_level(90) == RiskLevel.CRITICAL
        assert engine._risk_score_to_level(65) == RiskLevel.HIGH
        assert engine._risk_score_to_level(35) == RiskLevel.MEDIUM
        assert engine._risk_score_to_level(10) == RiskLevel.LOW

    def test_determine_status_compliant(self, engine):
        """Test compliance status determination - compliant"""
        assert engine._determine_compliance_status([]) == ComplianceStatus.COMPLIANT

    def test_determine_status_non_compliant(self, engine):
        """Test compliance status determination - non compliant"""
        violations = [
            ComplianceViolation(
                rule_id="test",
                activity_id="test",
                description="Critical issue",
                risk_level=RiskLevel.CRITICAL,
                remediation_actions=[]
            )
        ]
        assert engine._determine_compliance_status(violations) == ComplianceStatus.NON_COMPLIANT

    def test_calculate_score_perfect(self, engine):
        """Test score calculation with no violations"""
        score = engine._calculate_compliance_score([], [])
        assert score == 100.0

    def test_generate_mitigation_measures(self, engine):
        """Test mitigation measure generation"""
        activities = [
            DataProcessingActivity(
                id="test",
                name="Test",
                purpose="Test",
                data_types=[DataType.SENSITIVE_DATA],
                legal_bases=["consent"],
                retention_period=365,
                recipients=["third_party"],
                cross_border_transfers=True,
                automated_decision_making=True
            )
        ]

        measures = engine._generate_mitigation_measures(activities, RiskLevel.HIGH)
        assert isinstance(measures, list)
        assert len(measures) > 0


class TestModelsComprehensive:
    """Comprehensive model tests"""

    def test_data_types_enum(self):
        """Test DataType enum values"""
        assert DataType.PERSONAL_DATA == "personal_data"
        assert DataType.SENSITIVE_DATA == "sensitive_data"
        assert DataType.FINANCIAL_DATA == "financial_data"
        assert DataType.HEALTH_DATA == "health_data"

    def test_risk_levels_enum(self):
        """Test RiskLevel enum values"""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_compliance_status_enum(self):
        """Test ComplianceStatus enum values"""
        assert ComplianceStatus.COMPLIANT == "compliant"
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"
        assert ComplianceStatus.REQUIRES_REVIEW == "requires_review"
        assert ComplianceStatus.UNKNOWN == "unknown"

    def test_compliance_frameworks_enum(self):
        """Test ComplianceFramework enum values"""
        assert ComplianceFramework.PDPA_SINGAPORE == "pdpa_singapore"
        assert ComplianceFramework.GDPR_EU == "gdpr_eu"
        assert ComplianceFramework.CCPA_CALIFORNIA == "ccpa_california"
        assert ComplianceFramework.ISO_27001 == "iso_27001"

    def test_data_processing_activity_model(self):
        """Test DataProcessingActivity model"""
        activity = DataProcessingActivity(
            id="test_activity",
            name="Test Activity",
            purpose="Testing",
            data_types=[DataType.PERSONAL_DATA],
            legal_bases=["consent"],
            retention_period=365,
            recipients=["internal"],
            cross_border_transfers=False,
            automated_decision_making=False
        )

        assert activity.id == "test_activity"
        assert activity.name == "Test Activity"
        assert DataType.PERSONAL_DATA in activity.data_types

    def test_compliance_violation_model(self):
        """Test ComplianceViolation model"""
        violation = ComplianceViolation(
            rule_id="rule_001",
            activity_id="activity_001",
            description="Test violation",
            risk_level=RiskLevel.MEDIUM,
            remediation_actions=["Action 1", "Action 2"]
        )

        assert violation.rule_id == "rule_001"
        assert violation.risk_level == RiskLevel.MEDIUM
        assert len(violation.remediation_actions) == 2

    def test_data_subject_model(self):
        """Test DataSubject model"""
        subject = DataSubject(
            id="subject_001",
            region="Singapore",
            consent_status=True,
            consent_timestamp=datetime.utcnow(),
            data_types=[DataType.PERSONAL_DATA]
        )

        assert subject.id == "subject_001"
        assert subject.consent_status is True
        assert subject.region == "Singapore"



class TestUtilityFunctions:
    """Test utility functions and helpers"""

    def test_logger_import(self):
        """Test logger can be imported"""
        from src.compliance_agent.utils.logger import get_logger
        logger = get_logger("test")
        assert logger is not None

    def test_models_import(self):
        """Test models can be imported"""
        from src.compliance_agent.models.compliance_models import (
            DataType, RiskLevel, ComplianceStatus, ComplianceFramework
        )
        assert DataType.PERSONAL_DATA is not None
        assert RiskLevel.HIGH is not None
        assert ComplianceStatus.COMPLIANT is not None
        assert ComplianceFramework.PDPA_SINGAPORE is not None

    def test_init_imports(self):
        """Test package __init__ imports"""
        from src.compliance_agent.models import DataType
        from src.compliance_agent.services import ComplianceRuleEngine
        from src.compliance_agent.core import ComplianceEngine
        from src.compliance_agent.utils import get_logger

        assert DataType is not None
        assert ComplianceRuleEngine is not None
        assert ComplianceEngine is not None
        assert get_logger is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
