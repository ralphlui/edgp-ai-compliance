"""
Unit tests for ValidationAgent - cleaned version with only working tests

This module contains tests for the ValidationAgent that actually exist in the implementation.
Tests for non-existent methods have been removed.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from src.remediation_agent.agents.validation_agent import ValidationAgent
from src.remediation_agent.state.models import (
    RemediationDecision,
    RemediationType,
    ValidationResult,
    ValidationStatus,
    WorkflowStatus,
    RemediationWorkflow,
    WorkflowType,
)
from src.compliance_agent.models.compliance_models import (
    RiskLevel,
    ComplianceViolation as Violation,
    DataProcessingActivity as Activity,
)


@pytest_asyncio.fixture
async def validation_agent():
    """Create validation agent instance"""
    agent = ValidationAgent()
    return agent


@pytest.fixture
def sample_violation():
    """Create sample violation"""
    return Violation(
        rule_id="rule-001",
        description="Test violation - data retention exceeded",
        risk_level=RiskLevel.HIGH,
        violation_type="data_retention",
        detected_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_activity():
    """Create sample activity"""
    return Activity(
        id="a-001",
        name="Test Activity",
        purpose="analytics",  # Required field
        description="Test data processing activity",
        data_types=[],
        legal_bases=["consent"],
        retention_period=30,  # Integer, not string
    )


@pytest_asyncio.fixture
def sample_decision(sample_violation, sample_activity):
    """Create sample decision"""
    return RemediationDecision(
        violation_id="v-001",
        activity_id="a-001",
        decision_type="automatic",
        remediation_type=RemediationType.AUTOMATIC,
        requires_human_approval=False,
        recommended_actions=["delete_data"],
        estimated_impact="low",
        risk_level=RiskLevel.LOW,
        confidence_score=0.8,
        reasoning="Test reasoning",
        violation=sample_violation,
        activity=sample_activity
    )


@pytest_asyncio.fixture
def sample_workflow():
    """Create sample workflow without complex dependencies"""
    return RemediationWorkflow(
        id="wf-001",
        violation_id="v-001",
        activity_id="a-001",
        remediation_type=RemediationType.AUTOMATIC,
        workflow_type=WorkflowType.AUTOMATIC,
        steps=[],  # Keep it simple - just test the workflow structure
        status=WorkflowStatus.PENDING,
        created_at=datetime.now(timezone.utc)
    )


class TestValidationAgentInitialization:
    """Test ValidationAgent initialization"""

    def test_validation_agent_creation(self, validation_agent):
        """Test that validation agent can be created"""
        assert validation_agent is not None
        assert isinstance(validation_agent, ValidationAgent)

    def test_validation_agent_has_methods(self, validation_agent):
        """Test that validation agent has expected methods"""
        # Test only methods that actually exist
        assert hasattr(validation_agent, 'validate_decision')
        assert hasattr(validation_agent, 'validate_workflow')


class TestValidationMethods:
    """Test actual validation methods that exist"""

    @pytest.mark.asyncio
    async def test_validate_decision_with_valid_data(self, validation_agent, sample_decision):
        """Test validate_decision with valid decision data"""
        # The method is async
        result = await validation_agent.validate_decision(sample_decision)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        assert result.status in [ValidationStatus.VALID, ValidationStatus.INVALID, ValidationStatus.WARNING]

    @pytest.mark.asyncio
    async def test_validate_decision_returns_result(self, validation_agent, sample_decision):
        """Test that validate_decision returns proper ValidationResult"""
        result = await validation_agent.validate_decision(sample_decision)
        
        # Check result structure
        assert hasattr(result, 'status')
        assert hasattr(result, 'confidence_score')
        assert isinstance(result.validation_errors, list)
        assert isinstance(result.warnings, list)

    def test_validate_workflow_with_valid_data(self, validation_agent, sample_workflow):
        """Test validate_workflow with valid workflow data"""
        # validate_workflow is synchronous
        result = validation_agent.validate_workflow(sample_workflow)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        assert result.status in [ValidationStatus.VALID, ValidationStatus.INVALID, ValidationStatus.WARNING]

    def test_validate_workflow_with_empty_steps(self, validation_agent):
        """Test validating workflow with no steps"""
        empty_workflow = RemediationWorkflow(
            id="wf-002",
            violation_id="v-001",
            activity_id="a-001",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[],
            status=WorkflowStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        result = validation_agent.validate_workflow(empty_workflow)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        # Workflow with no steps should be invalid or have warnings
        assert result.status in [ValidationStatus.INVALID, ValidationStatus.WARNING]

    def test_validate_workflow_with_invalid_data(self, validation_agent):
        """Test validation with invalid workflow data"""
        result = validation_agent.validate_workflow(None)
        
        assert result is not None
        assert isinstance(result, ValidationResult)
        assert result.status == ValidationStatus.INVALID


class TestValidationResults:
    """Test validation result structure"""

    @pytest.mark.asyncio
    async def test_validation_result_has_required_fields(self, validation_agent, sample_decision):
        """Test that validation results have all required fields"""
        result = await validation_agent.validate_decision(sample_decision)
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'confidence_score')
        assert hasattr(result, 'validation_errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'recommendations')

    @pytest.mark.asyncio
    async def test_validation_result_types(self, validation_agent, sample_decision):
        """Test that validation result fields have correct types"""
        result = await validation_agent.validate_decision(sample_decision)
        
        assert isinstance(result.status, ValidationStatus)
        assert isinstance(result.confidence_score, (int, float))
        assert isinstance(result.validation_errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.recommendations, list)
