"""
Enhanced unit tests for validation agent with high coverage
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.remediation_agent.agents.validation_agent import ValidationAgent
from src.remediation_agent.state.models import (
    RemediationDecision, RemediationWorkflow, WorkflowStep, 
    RemediationType, WorkflowStatus
)
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation, RiskLevel, DataProcessingActivity, 
    ComplianceFramework, DataType
)


class TestValidationAgentEnhanced:
    """Enhanced tests for ValidationAgent with high coverage"""
    
    @pytest.fixture
    def validation_agent(self):
        """Create a validation agent instance"""
        return ValidationAgent()
    
    @pytest.fixture
    def sample_violation(self):
        """Create a sample compliance violation"""
        return ComplianceViolation(
            id="violation-123",
            violation_type="unauthorized_data_processing",
            description="Processing personal data without consent",
            risk_level=RiskLevel.HIGH,
            framework=ComplianceFramework.GDPR_EU,
            data_subject_id="user-456",
            affected_data_types=[DataType.PERSONAL_DATA],
            remediation_actions=["Stop data processing", "Delete personal data"],
            evidence={"log_entry": "Unauthorized access detected"},
            detection_timestamp="2024-01-15T10:30:00Z"
        )
    
    @pytest.fixture
    def sample_activity(self):
        """Create a sample data processing activity"""
        return DataProcessingActivity(
            id="activity-123",
            name="User Analytics",
            description="Analyzing user behavior patterns",
            purpose="analytics",
            data_controller="Analytics Team",
            data_processor="Data Science Dept",
            data_types=[DataType.PERSONAL_DATA],
            legal_basis="legitimate_interest",
            retention_period_days=365,
            data_subjects=["users"],
            third_party_sharing=False,
            cross_border_transfer=False,
            automated_decision_making=True
        )
    
    @pytest.fixture
    def sample_decision(self, sample_violation, sample_activity):
        """Create a sample remediation decision"""
        return RemediationDecision(
            violation_id=sample_violation.id,
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.85,
            reasoning="Low risk operation with clear remediation path",
            estimated_effort=30,
            risk_if_delayed=RiskLevel.MEDIUM
        )
    
    @pytest.fixture
    def sample_workflow(self, sample_decision):
        """Create a sample remediation workflow"""
        steps = [
            WorkflowStep(
                id="step-1",
                name="Stop Data Processing",
                description="Stop the data processing activity",
                action_type="api_call",
                parameters={"endpoint": "/api/stop-processing", "activity_id": "activity-123"}
            ),
            WorkflowStep(
                id="step-2", 
                name="Delete Personal Data",
                description="Delete user personal data",
                action_type="database_operation",
                parameters={"query": "DELETE FROM users WHERE id = 'user-456'"}
            )
        ]
        
        return RemediationWorkflow(
            id="workflow-123",
            violation_id=sample_decision.violation_id,
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=steps
        )
    
    @pytest.mark.asyncio
    async def test_validate_decision_valid_automatic(self, validation_agent, sample_decision):
        """Test validation of valid automatic decision"""
        # Mock the validation methods that would be called
        with patch.object(validation_agent, '_check_decision_constraints') as mock_constraints:
            mock_constraints.return_value = True
            
            with patch.object(validation_agent, '_validate_decision_logic') as mock_logic:
                mock_logic.return_value = {
                    "is_valid": True,
                    "confidence": 0.9,
                    "issues": [],
                    "recommendations": []
                }
                
                # Test the validation - assume it returns a dict
                result = await validation_agent.validate_decision(sample_decision)
                
                assert isinstance(result, dict)
                assert result.get("is_valid") is True
                assert result.get("confidence", 0) >= 0.8
                mock_constraints.assert_called_once_with(sample_decision)
                mock_logic.assert_called_once_with(sample_decision)
    
    @pytest.mark.asyncio
    async def test_validate_decision_invalid_constraints(self, validation_agent, sample_decision):
        """Test validation of decision that violates constraints"""
        with patch.object(validation_agent, '_check_decision_constraints') as mock_constraints:
            mock_constraints.return_value = False
            
            result = await validation_agent.validate_decision(sample_decision)
            
            assert isinstance(result, dict)
            assert result.get("is_valid") is False
            assert len(result.get("issues", [])) > 0
    
    @pytest.mark.asyncio
    async def test_validate_decision_warning_conditions(self, validation_agent, sample_decision):
        """Test validation with warning conditions"""
        sample_decision.confidence_score = 0.65  # Medium confidence
        
        with patch.object(validation_agent, '_check_decision_constraints') as mock_constraints:
            mock_constraints.return_value = True
            
            with patch.object(validation_agent, '_validate_decision_logic') as mock_logic:
                mock_logic.return_value = {
                    "is_valid": True,
                    "confidence": 0.65,
                    "issues": ["Medium confidence score"],
                    "recommendations": ["Consider manual review"]
                }
                
                result = await validation_agent.validate_decision(sample_decision)
                
                assert result.get("is_valid") is True
                assert result.get("confidence") == 0.65
                assert len(result.get("issues", [])) > 0
    
    @pytest.mark.asyncio
    async def test_validate_workflow_valid(self, validation_agent, sample_workflow):
        """Test validation of valid workflow"""
        with patch.object(validation_agent, '_validate_workflow_structure') as mock_structure:
            mock_structure.return_value = {"is_valid": True, "issues": []}
            
            with patch.object(validation_agent, '_validate_workflow_steps') as mock_steps:
                mock_steps.return_value = {"is_valid": True, "issues": []}
                
                with patch.object(validation_agent, '_check_workflow_feasibility') as mock_feasibility:
                    mock_feasibility.return_value = {"is_feasible": True, "confidence": 0.9, "issues": []}
                    
                    result = await validation_agent.validate_workflow(sample_workflow)
                    
                    assert isinstance(result, dict)
                    assert result.get("is_valid") is True
                    assert result.get("confidence", 0) >= 0.8
    
    def test_check_decision_constraints_valid(self, validation_agent, sample_decision):
        """Test decision constraint checking for valid decision"""
        result = validation_agent._check_decision_constraints(sample_decision)
        
        assert result is True
    
    def test_check_decision_constraints_invalid_confidence(self, validation_agent, sample_decision):
        """Test decision constraint checking for invalid confidence score"""
        sample_decision.confidence_score = 1.5  # Invalid: > 1
        
        result = validation_agent._check_decision_constraints(sample_decision)
        
        assert result is False
    
    def test_check_decision_constraints_negative_effort(self, validation_agent, sample_decision):
        """Test decision constraint checking for negative effort"""
        sample_decision.estimated_effort = -10  # Invalid
        
        result = validation_agent._check_decision_constraints(sample_decision)
        
        assert result is False
    
    def test_validate_decision_logic_high_confidence_automatic(self, validation_agent, sample_decision):
        """Test decision logic validation for high confidence automatic decision"""
        sample_decision.confidence_score = 0.95
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        
        result = validation_agent._validate_decision_logic(sample_decision)
        
        assert result["is_valid"] is True
        assert result["confidence"] >= 0.9
        assert len(result["issues"]) == 0
    
    def test_validate_decision_logic_low_confidence_automatic(self, validation_agent, sample_decision):
        """Test decision logic validation for low confidence automatic decision"""
        sample_decision.confidence_score = 0.4  # Low confidence
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        
        result = validation_agent._validate_decision_logic(sample_decision)
        
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert any("confidence" in issue.lower() for issue in result["issues"])
    
    def test_validate_decision_logic_high_effort_automatic(self, validation_agent, sample_decision):
        """Test decision logic validation for high effort automatic decision"""
        sample_decision.estimated_effort = 500  # Very high effort
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        
        result = validation_agent._validate_decision_logic(sample_decision)
        
        assert result["is_valid"] is False
        assert any("effort" in issue.lower() for issue in result["issues"])
    
    def test_validate_decision_logic_manual_only_appropriate(self, validation_agent, sample_decision):
        """Test decision logic validation for appropriate manual-only decision"""
        sample_decision.remediation_type = RemediationType.MANUAL_ONLY
        sample_decision.risk_if_delayed = RiskLevel.CRITICAL
        sample_decision.estimated_effort = 480
        
        result = validation_agent._validate_decision_logic(sample_decision)
        
        assert result["is_valid"] is True
        assert result["confidence"] >= 0.7
    
    def test_validate_workflow_structure_valid(self, validation_agent, sample_workflow):
        """Test workflow structure validation for valid workflow"""
        result = validation_agent._validate_workflow_structure(sample_workflow)
        
        assert result["is_valid"] is True
        assert len(result["issues"]) == 0
    
    def test_validate_workflow_structure_empty_steps(self, validation_agent, sample_workflow):
        """Test workflow structure validation for workflow with no steps"""
        sample_workflow.steps = []
        
        result = validation_agent._validate_workflow_structure(sample_workflow)
        
        assert result["is_valid"] is False
        assert any("empty" in issue.lower() or "no steps" in issue.lower() for issue in result["issues"])
    
    def test_validate_workflow_structure_missing_ids(self, validation_agent, sample_workflow):
        """Test workflow structure validation for missing required IDs"""
        sample_workflow.violation_id = None
        
        result = validation_agent._validate_workflow_structure(sample_workflow)
        
        assert result["is_valid"] is False
        assert any("id" in issue.lower() for issue in result["issues"])
    
    def test_validate_workflow_steps_valid(self, validation_agent, sample_workflow):
        """Test workflow steps validation for valid steps"""
        result = validation_agent._validate_workflow_steps(sample_workflow)
        
        assert result["is_valid"] is True
        assert len(result["issues"]) == 0
    
    def test_validate_workflow_steps_missing_parameters(self, validation_agent, sample_workflow):
        """Test workflow steps validation for missing parameters"""
        sample_workflow.steps[0].parameters = {}  # Remove parameters
        
        result = validation_agent._validate_workflow_steps(sample_workflow)
        
        assert result["is_valid"] is False
        assert any("parameters" in issue.lower() for issue in result["issues"])
    
    def test_validate_workflow_steps_invalid_action_type(self, validation_agent, sample_workflow):
        """Test workflow steps validation for invalid action type"""
        sample_workflow.steps[0].action_type = "invalid_action"
        
        result = validation_agent._validate_workflow_steps(sample_workflow)
        
        assert result["is_valid"] is False
        assert any("action" in issue.lower() for issue in result["issues"])
    
    def test_validate_workflow_steps_duplicate_ids(self, validation_agent, sample_workflow):
        """Test workflow steps validation for duplicate step IDs"""
        sample_workflow.steps[1].id = sample_workflow.steps[0].id  # Duplicate ID
        
        result = validation_agent._validate_workflow_steps(sample_workflow)
        
        assert result["is_valid"] is False
        assert any("duplicate" in issue.lower() for issue in result["issues"])
    
    def test_check_workflow_feasibility_high_feasibility(self, validation_agent, sample_workflow):
        """Test workflow feasibility check for highly feasible workflow"""
        result = validation_agent._check_workflow_feasibility(sample_workflow)
        
        assert result["is_feasible"] is True
        assert result["confidence"] >= 0.7
        assert len(result["issues"]) <= 1
    
    def test_calculate_validation_confidence_high(self, validation_agent):
        """Test validation confidence calculation for high confidence scenario"""
        factors = {
            "constraint_check": True,
            "logic_validation": {"confidence": 0.9, "issues": []},
            "decision_complexity": 0.2,
            "consistency_score": 0.95
        }
        
        confidence = validation_agent._calculate_validation_confidence(factors)
        
        assert confidence >= 0.8
    
    def test_calculate_validation_confidence_low(self, validation_agent):
        """Test validation confidence calculation for low confidence scenario"""
        factors = {
            "constraint_check": False,
            "logic_validation": {"confidence": 0.4, "issues": ["Multiple issues"]},
            "decision_complexity": 0.9,
            "consistency_score": 0.3
        }
        
        confidence = validation_agent._calculate_validation_confidence(factors)
        
        assert confidence <= 0.5
    
    def test_assess_decision_complexity_simple(self, validation_agent, sample_decision):
        """Test decision complexity assessment for simple decision"""
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        sample_decision.estimated_effort = 15
        
        complexity = validation_agent._assess_decision_complexity(sample_decision)
        
        assert complexity <= 0.4
    
    def test_assess_decision_complexity_complex(self, validation_agent, sample_decision):
        """Test decision complexity assessment for complex decision"""
        sample_decision.remediation_type = RemediationType.MANUAL_ONLY
        sample_decision.estimated_effort = 480
        sample_decision.risk_if_delayed = RiskLevel.CRITICAL
        
        complexity = validation_agent._assess_decision_complexity(sample_decision)
        
        assert complexity >= 0.6
    
    def test_check_decision_consistency_consistent(self, validation_agent, sample_decision):
        """Test decision consistency check for consistent decision"""
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        sample_decision.confidence_score = 0.9
        sample_decision.estimated_effort = 20
        
        consistency = validation_agent._check_decision_consistency(sample_decision)
        
        assert consistency >= 0.8
    
    def test_check_decision_consistency_inconsistent(self, validation_agent, sample_decision):
        """Test decision consistency check for inconsistent decision"""
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        sample_decision.confidence_score = 0.3  # Low confidence for automatic
        sample_decision.estimated_effort = 300  # High effort for automatic
        
        consistency = validation_agent._check_decision_consistency(sample_decision)
        
        assert consistency <= 0.5
    
    def test_get_validation_recommendations_automatic_low_confidence(self, validation_agent, sample_decision):
        """Test validation recommendations for automatic decision with low confidence"""
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        sample_decision.confidence_score = 0.4
        
        recommendations = validation_agent._get_validation_recommendations(sample_decision)
        
        assert len(recommendations) > 0
        assert any("confidence" in rec.lower() for rec in recommendations)
    
    def test_get_validation_recommendations_high_effort_automatic(self, validation_agent, sample_decision):
        """Test validation recommendations for high effort automatic decision"""
        sample_decision.remediation_type = RemediationType.AUTOMATIC
        sample_decision.estimated_effort = 400
        
        recommendations = validation_agent._get_validation_recommendations(sample_decision)
        
        assert len(recommendations) > 0
        assert any("effort" in rec.lower() or "manual" in rec.lower() for rec in recommendations)
    
    def test_validate_step_parameters_api_call(self, validation_agent):
        """Test step parameter validation for API call"""
        step = WorkflowStep(
            id="step-1",
            name="API Call",
            description="Test API call",
            action_type="api_call",
            parameters={"endpoint": "/api/test", "method": "POST"}
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is True
    
    def test_validate_step_parameters_api_call_missing_endpoint(self, validation_agent):
        """Test step parameter validation for API call missing endpoint"""
        step = WorkflowStep(
            id="step-1",
            name="API Call",
            description="Test API call",
            action_type="api_call",
            parameters={"method": "POST"}  # Missing endpoint
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is False
    
    def test_validate_step_parameters_database_operation(self, validation_agent):
        """Test step parameter validation for database operation"""
        step = WorkflowStep(
            id="step-1",
            name="Database Operation",
            description="Test database operation",
            action_type="database_operation",
            parameters={"query": "DELETE FROM users WHERE id = ?"}
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is True
    
    def test_validate_step_parameters_database_operation_missing_query(self, validation_agent):
        """Test step parameter validation for database operation missing query"""
        step = WorkflowStep(
            id="step-1",
            name="Database Operation",
            description="Test database operation",
            action_type="database_operation",
            parameters={"table": "users"}  # Missing query
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is False
    
    def test_validate_step_parameters_unsupported_action(self, validation_agent):
        """Test step parameter validation for unsupported action type"""
        step = WorkflowStep(
            id="step-1",
            name="Unknown Action",
            description="Test unknown action",
            action_type="unsupported_action",
            parameters={"param": "value"}
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is False
    
    def test_estimate_workflow_risk_low_risk(self, validation_agent, sample_workflow):
        """Test workflow risk estimation for low risk workflow"""
        # Simple, short workflow
        sample_workflow.steps = sample_workflow.steps[:1]  # Just one simple step
        
        risk_score = validation_agent._estimate_workflow_risk(sample_workflow)
        
        assert risk_score <= 0.5
    
    def test_estimate_workflow_risk_high_risk(self, validation_agent, sample_workflow):
        """Test workflow risk estimation for high risk workflow"""
        # Complex, long workflow with database operations
        sample_workflow.steps[1].action_type = "database_operation"
        sample_workflow.steps[1].parameters = {
            "query": "DELETE FROM sensitive_data WHERE condition = 'complex'"
        }
        
        # Add more complex steps
        for i in range(5):
            sample_workflow.steps.append(
                WorkflowStep(
                    id=f"step-{i+3}",
                    name=f"Complex Step {i+1}",
                    description=f"Complex operation {i+1}",
                    action_type="database_operation",
                    parameters={"query": f"COMPLEX QUERY {i+1}"}
                )
            )
        
        risk_score = validation_agent._estimate_workflow_risk(sample_workflow)
        
        assert risk_score >= 0.4


class TestValidationAgentEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def validation_agent(self):
        return ValidationAgent()
    
    @pytest.mark.asyncio
    async def test_validate_decision_none_input(self, validation_agent):
        """Test validation with None decision input"""
        result = await validation_agent.validate_decision(None)
        
        assert isinstance(result, dict)
        assert result.get("is_valid") is False
        assert len(result.get("issues", [])) > 0
    
    @pytest.mark.asyncio
    async def test_validate_workflow_none_input(self, validation_agent):
        """Test validation with None workflow input"""
        result = await validation_agent.validate_workflow(None)
        
        assert isinstance(result, dict)
        assert result.get("is_valid") is False
        assert len(result.get("issues", [])) > 0
    
    def test_validate_step_parameters_none_parameters(self, validation_agent):
        """Test step parameter validation with None parameters"""
        step = WorkflowStep(
            id="step-1",
            name="Test Step",
            description="Test step",
            action_type="api_call",
            parameters=None
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is False
    
    def test_validate_step_parameters_empty_parameters(self, validation_agent):
        """Test step parameter validation with empty parameters"""
        step = WorkflowStep(
            id="step-1",
            name="Test Step",
            description="Test step",
            action_type="api_call",
            parameters={}
        )
        
        is_valid = validation_agent._validate_step_parameters(step)
        
        assert is_valid is False
    
    def test_calculate_validation_confidence_missing_factors(self, validation_agent):
        """Test validation confidence calculation with missing factors"""
        factors = {
            "constraint_check": True
            # Missing other factors
        }
        
        confidence = validation_agent._calculate_validation_confidence(factors)
        
        assert 0.0 <= confidence <= 1.0  # Should handle gracefully
    
    def test_estimate_workflow_risk_empty_workflow(self, validation_agent):
        """Test workflow risk estimation with empty workflow"""
        from src.remediation_agent.state.models import RemediationWorkflow, WorkflowType
        
        workflow = RemediationWorkflow(
            id="empty-workflow",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[]
        )
        
        risk_score = validation_agent._estimate_workflow_risk(workflow)
        
        assert risk_score == 1.0  # Maximum risk for empty workflow