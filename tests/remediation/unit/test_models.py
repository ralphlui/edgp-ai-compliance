"""
Unit tests for remediation agent state models
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError

from src.remediation_agent.state.models import (
    RemediationDecision,
    RemediationType,
    WorkflowStep,
    WorkflowStatus,
    WorkflowType,
    RemediationWorkflow,
    RemediationSignal,
    HumanTask,
    RemediationMetrics,
    SignalType,
    UrgencyLevel,
    utc_now
)
from src.compliance_agent.models.compliance_models import RiskLevel


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_utc_now_returns_utc_timezone(self):
        """Test that utc_now returns UTC timezone"""
        now = utc_now()
        assert now.tzinfo == timezone.utc
        assert isinstance(now, datetime)


class TestEnums:
    """Test enumeration classes"""
    
    def test_remediation_type_enum(self):
        """Test RemediationType enum values"""
        assert RemediationType.AUTOMATIC == "automatic"
        assert RemediationType.HUMAN_IN_LOOP == "human_in_loop"
        assert RemediationType.MANUAL_ONLY == "manual_only"
        
        # Test enum membership
        assert "automatic" in RemediationType._value2member_map_
        assert "human_in_loop" in RemediationType._value2member_map_
        assert "manual_only" in RemediationType._value2member_map_
    
    def test_workflow_status_enum(self):
        """Test WorkflowStatus enum values"""
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.IN_PROGRESS == "in_progress"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.CANCELLED == "cancelled"
        assert WorkflowStatus.REQUIRES_HUMAN == "requires_human"
    
    def test_workflow_type_enum(self):
        """Test WorkflowType enum values"""
        assert WorkflowType.AUTOMATIC == "automatic"
        assert WorkflowType.HUMAN_IN_LOOP == "human_in_loop"
        assert WorkflowType.MANUAL_ONLY == "manual_only"


class TestRemediationDecision:
    """Test RemediationDecision model"""
    
    def test_valid_remediation_decision_creation(self, sample_remediation_decision):
        """Test creating a valid remediation decision"""
        decision = sample_remediation_decision
        
        assert decision.remediation_type == RemediationType.HUMAN_IN_LOOP
        assert decision.confidence_score == 0.85
        assert decision.reasoning == "High-risk operation requires human oversight for data deletion"
        assert decision.estimated_effort == 60
        assert "data_protection_officer_approval" in decision.prerequisites
        assert decision.risk_if_delayed == RiskLevel.HIGH
        # Field validation complete - model has all required fields
    
    def test_remediation_decision_validation(self):
        """Test validation of remediation decision fields"""
        # Test invalid confidence score (outside 0-1 range)
        with pytest.raises(ValidationError) as exc_info:
            RemediationDecision(
                violation_id="test_id",
                remediation_type=RemediationType.AUTOMATIC,
                confidence_score=1.5,  # Invalid: > 1
                reasoning="Test reasoning",
                estimated_effort=30,
                risk_if_delayed=RiskLevel.HIGH
            )
        assert "Input should be less than or equal to 1" in str(exc_info.value)
        
        # Test invalid estimated effort
        with pytest.raises(ValidationError) as exc_info:
            RemediationDecision(
                violation_id="test_id",
                remediation_type=RemediationType.AUTOMATIC,
                confidence_score=0.8,
                reasoning="Test reasoning",
                estimated_effort=-1,  # Invalid: negative
                risk_if_delayed=RiskLevel.HIGH
            )
        assert "Input should be greater than 0" in str(exc_info.value)
    
    def test_remediation_decision_defaults(self):
        """Test default values for optional fields"""
        decision = RemediationDecision(
            violation_id="test_id",
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.9,
            reasoning="Test reasoning",
            estimated_effort=30,
            risk_if_delayed=RiskLevel.HIGH
        )
        
        assert decision.estimated_effort == 30
        assert decision.prerequisites == []
        assert decision.risk_if_delayed == RiskLevel.HIGH
        # Default validation complete
        # Model complete with all required fields


class TestWorkflowStep:
    """Test WorkflowStep model"""
    
    def test_valid_workflow_step_creation(self, sample_workflow_step):
        """Test creating a valid workflow step"""
        step = sample_workflow_step
        
        assert step.name == "Delete User Data"
        assert step.action_type == "data_deletion"
        assert "user_id" in step.parameters
        assert step.parameters["user_id"] == "user_123"
        assert step.estimated_duration_minutes == 15
        assert step.order == 0
        assert step.retry_count == 0
    
    def test_workflow_step_defaults(self):
        """Test default values for workflow step"""
        step = WorkflowStep(
            id="step_123",
            name="Test Step",
            description="Test description",
            action_type="test_action"
        )
        
        assert step.parameters == {}
        assert step.retry_count == 0
        assert step.estimated_duration_minutes == 5
        assert step.status == WorkflowStatus.PENDING
    
    def test_workflow_step_validation(self):
        """Test validation of workflow step fields"""
        # Test negative duration
        with pytest.raises(ValidationError) as exc_info:
            WorkflowStep(
                id="step_123",
                name="Test Step",
                description="Test description",
                action_type="test_action",
                estimated_duration_minutes=-5  # Invalid: negative
            )
        assert "Input should be greater than 0" in str(exc_info.value)


class TestRemediationWorkflow:
    """Test RemediationWorkflow model"""
    
    def test_valid_remediation_workflow_creation(self, sample_remediation_workflow):
        """Test creating a valid remediation workflow"""
        workflow = sample_remediation_workflow
        
        assert workflow.workflow_type == WorkflowType.HUMAN_IN_LOOP
        assert workflow.status == WorkflowStatus.PENDING
        assert len(workflow.steps) == 1
        assert workflow.metadata["framework"] == "gdpr_eu"
        assert workflow.metadata["priority"] == "high"
    
    def test_workflow_defaults(self):
        """Test default values for workflow"""
        workflow = RemediationWorkflow(
            id="workflow_123",
            violation_id="violation_123",
            activity_id="activity_123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[]
        )
        
        assert workflow.status == WorkflowStatus.PENDING
        assert workflow.steps == []
        assert workflow.current_step_index == 0
        assert workflow.metadata == {}
    
    def test_workflow_validation(self):
        """Test validation of workflow fields"""
        # Test negative step index
        with pytest.raises(ValidationError) as exc_info:
            RemediationWorkflow(
                id="workflow_123",
                violation_id="violation_123",
                activity_id="activity_123",
                remediation_type=RemediationType.AUTOMATIC,
                workflow_type=WorkflowType.AUTOMATIC,
                steps=[],
                current_step_index=-1  # Invalid: negative
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


class TestRemediationSignal:
    """Test RemediationSignal model"""
    
    def test_valid_remediation_signal_creation(self, sample_remediation_signal, sample_compliance_violation, sample_data_processing_activity):
        """Test creating a valid remediation signal"""
        signal = sample_remediation_signal
        
        assert signal.violation_id == sample_compliance_violation.rule_id
        assert signal.activity_id == sample_data_processing_activity.id
        assert signal.signal_type == SignalType.COMPLIANCE_VIOLATION
        assert signal.priority == RiskLevel.HIGH
        assert "user_request_id" in signal.context
    
    def test_signal_defaults(self, sample_compliance_violation, sample_data_processing_activity):
        """Test default values for remediation signal"""
        signal = RemediationSignal(
            signal_id="signal_123",
            violation_id=sample_compliance_violation.rule_id,
            activity_id=sample_data_processing_activity.id,
            signal_type=SignalType.COMPLIANCE_VIOLATION,
            confidence_score=0.8,
            urgency_level=UrgencyLevel.MEDIUM,
            id="signal_123",
            priority=RiskLevel.MEDIUM
        )
        
        assert signal.priority == "medium"
        assert signal.context == {}
        assert isinstance(signal.created_at, datetime)


class TestHumanTask:
    """Test HumanTask model"""
    
    def test_valid_human_task_creation(self, sample_human_task):
        """Test creating a valid human task"""
        task = sample_human_task
        
        assert task.title == "Approve Data Deletion"
        assert task.assignee == "data_protection_officer"
        assert task.priority == RiskLevel.HIGH
        assert task.status == "pending"
    
    def test_human_task_defaults(self):
        """Test default values for human task"""
        task = HumanTask(
            id="task_123",
            workflow_id="workflow_123",
            title="Test Task",
            description="Test description",
            assignee="test_user"
        )
        
        assert task.priority == RiskLevel.MEDIUM
        assert task.status == "pending"
        assert isinstance(task.created_at, datetime)
        assert task.due_date is None
        assert task.completed_at is None
    
    def test_human_task_status_validation(self):
        """Test validation of human task status"""
        # Valid statuses should work
        valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
        for status in valid_statuses:
            task = HumanTask(
                id="task_123",
                workflow_id="workflow_123",
                title="Test Task",
                description="Test description",
                assignee="test_user",
                status=status
            )
            assert task.status == status


class TestRemediationMetrics:
    """Test RemediationMetrics model"""
    
    def test_valid_metrics_creation(self, sample_remediation_metrics):
        """Test creating valid remediation metrics"""
        metrics = sample_remediation_metrics
        
        assert metrics.total_violations_processed == 100
        assert metrics.automatic_remediations == 45
        assert metrics.human_loop_remediations == 35
        assert metrics.manual_remediations == 20
        assert metrics.success_rate == 0.85
        assert metrics.average_resolution_time == 120.5
        assert RiskLevel.HIGH in metrics.by_risk_level
        assert "gdpr_eu" in metrics.by_framework
    
    def test_metrics_defaults(self):
        """Test default values for metrics"""
        metrics = RemediationMetrics()
        
        assert metrics.total_violations_processed == 0
        assert metrics.automatic_remediations == 0
        assert metrics.human_loop_remediations == 0
        assert metrics.manual_remediations == 0
        assert metrics.success_rate == 0.0
        assert metrics.average_resolution_time == 0.0
        assert metrics.by_risk_level == {}
        assert metrics.by_framework == {}
    
    def test_metrics_validation(self):
        """Test validation of metrics fields"""
        # Test negative values
        with pytest.raises(ValidationError) as exc_info:
            RemediationMetrics(
                total_violations_processed=-1  # Invalid: negative
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
        
        # Test success rate validation
        with pytest.raises(ValidationError) as exc_info:
            RemediationMetrics(
                success_rate=1.5  # Invalid: > 1.0
            )
        assert "Input should be less than or equal to 1" in str(exc_info.value)
    
    def test_metrics_consistency_validation(self):
        """Test logical consistency of metrics"""
        # Total should equal sum of remediation types
        metrics = RemediationMetrics(
            total_violations_processed=100,
            automatic_remediations=30,
            human_loop_remediations=40,
            manual_remediations=30  # 30 + 40 + 30 = 100 ✓
        )
        assert metrics.total_violations_processed == (
            metrics.automatic_remediations + 
            metrics.human_loop_remediations + 
            metrics.manual_remediations
        )


class TestModelSerialization:
    """Test model serialization and deserialization"""
    
    def test_remediation_decision_serialization(self, sample_remediation_decision):
        """Test serializing remediation decision to dict and back"""
        decision = sample_remediation_decision
        
        # Serialize to dict
        decision_dict = decision.dict()
        assert isinstance(decision_dict, dict)
        assert decision_dict["remediation_type"] == "human_in_loop"
        assert decision_dict["confidence_score"] == 0.85
        
        # Deserialize back to model
        new_decision = RemediationDecision(**decision_dict)
        assert new_decision.violation_id == decision.violation_id
        assert new_decision.remediation_type == decision.remediation_type
        assert new_decision.confidence_score == decision.confidence_score
    
    def test_workflow_serialization(self, sample_remediation_workflow):
        """Test serializing workflow to dict and back"""
        workflow = sample_remediation_workflow
        
        # Serialize to dict
        workflow_dict = workflow.dict()
        assert isinstance(workflow_dict, dict)
        assert workflow_dict["workflow_type"] == "human_in_loop"
        assert len(workflow_dict["steps"]) == 1
        
        # Deserialize back to model
        new_workflow = RemediationWorkflow(**workflow_dict)
        assert new_workflow.id == workflow.id
        assert new_workflow.workflow_type == workflow.workflow_type
        assert len(new_workflow.steps) == len(workflow.steps)
    
    def test_json_serialization(self, sample_remediation_signal):
        """Test JSON serialization"""
        signal = sample_remediation_signal
        
        # Test JSON serialization
        json_str = signal.json()
        assert isinstance(json_str, str)
        
        # Test JSON deserialization
        # Test JSON deserialization\n        new_signal = RemediationSignal.parse_raw(json_str)\n        assert new_signal.id == signal.id\n        assert new_signal.signal_type == signal.signal_type