"""
Improved unit tests for remediation agent models with correct field names
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.remediation_agent.state.models import (
    RemediationDecision,
    WorkflowStep,
    RemediationWorkflow,
    RemediationSignal,
    HumanTask,
    RemediationMetrics,
    RemediationType,
    WorkflowStatus,
    WorkflowType,
    utc_now
)
from src.compliance_agent.models.compliance_models import RiskLevel


class TestModelsFixed:
    """Fixed tests that match actual model structure"""
    
    def test_remediation_decision_creation(self):
        """Test creating a valid RemediationDecision"""
        decision = RemediationDecision(
            violation_id="violation-123",
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.9,
            reasoning="Simple data update operation",
            estimated_effort=15,
            risk_if_delayed=RiskLevel.LOW
        )
        
        assert decision.violation_id == "violation-123"
        assert decision.remediation_type == RemediationType.AUTOMATIC
        assert decision.confidence_score == 0.9
        assert decision.reasoning == "Simple data update operation"
        assert decision.estimated_effort == 15
        assert decision.risk_if_delayed == RiskLevel.LOW
        assert decision.prerequisites == []  # Default value
    
    def test_remediation_decision_validation(self):
        """Test RemediationDecision validation"""
        # Test invalid confidence score
        with pytest.raises(ValidationError) as exc_info:
            RemediationDecision(
                violation_id="violation-123",
                remediation_type=RemediationType.AUTOMATIC,
                confidence_score=1.5,  # Invalid: > 1
                reasoning="Test reasoning",
                estimated_effort=15,
                risk_if_delayed=RiskLevel.LOW
            )
        assert "Input should be less than or equal to 1" in str(exc_info.value)
        
        # Test negative confidence score
        with pytest.raises(ValidationError) as exc_info:
            RemediationDecision(
                violation_id="violation-123",
                remediation_type=RemediationType.AUTOMATIC,
                confidence_score=-0.1,  # Invalid: < 0
                reasoning="Test reasoning",
                estimated_effort=15,
                risk_if_delayed=RiskLevel.LOW
            )
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
    
    def test_workflow_step_creation(self):
        """Test creating a valid WorkflowStep"""
        step = WorkflowStep(
            id="step-123",
            name="Update User Preference",
            description="Update user email preference to opt-out",
            action_type="data_update"
        )
        
        assert step.id == "step-123"
        assert step.name == "Update User Preference"
        assert step.description == "Update user email preference to opt-out"
        assert step.action_type == "data_update"
        assert step.status == WorkflowStatus.PENDING  # Default value
        assert step.retry_count == 0  # Default value
        assert step.max_retries == 3  # Default value
        assert step.parameters == {}  # Default value
    
    def test_workflow_step_with_parameters(self):
        """Test WorkflowStep with custom parameters"""
        step = WorkflowStep(
            id="step-123",
            name="API Call",
            description="Call external API",
            action_type="api_call",
            parameters={"url": "https://api.example.com", "method": "POST"},
            max_retries=5
        )
        
        assert step.parameters["url"] == "https://api.example.com"
        assert step.parameters["method"] == "POST"
        assert step.max_retries == 5
    
    def test_remediation_workflow_creation(self):
        """Test creating a valid RemediationWorkflow"""
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC
        )
        
        assert workflow.id == "workflow-123"
        assert workflow.violation_id == "violation-123"
        assert workflow.activity_id == "activity-123"
        assert workflow.remediation_type == RemediationType.AUTOMATIC
        assert workflow.workflow_type == WorkflowType.AUTOMATIC
        assert workflow.status == WorkflowStatus.PENDING  # Default value
        assert workflow.steps == []  # Default value
        assert workflow.priority == RiskLevel.MEDIUM  # Default value
        assert isinstance(workflow.created_at, datetime)
    
    def test_remediation_workflow_with_steps(self):
        """Test RemediationWorkflow with steps"""
        steps = [
            WorkflowStep(
                id="step-1",
                name="Step 1",
                description="First step",
                action_type="data_update"
            ),
            WorkflowStep(
                id="step-2",
                name="Step 2", 
                description="Second step",
                action_type="notification"
            )
        ]
        
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.HUMAN_IN_LOOP,
            workflow_type=WorkflowType.HUMAN_IN_LOOP,
            steps=steps,
            priority=RiskLevel.HIGH
        )
        
        assert len(workflow.steps) == 2
        assert workflow.steps[0].id == "step-1"
        assert workflow.steps[1].id == "step-2"
        assert workflow.priority == RiskLevel.HIGH
    
    def test_human_task_creation(self):
        """Test creating a valid HumanTask"""
        task = HumanTask(
            id="task-123",
            workflow_id="workflow-123",
            title="Review Data Deletion",
            description="Review and approve data deletion request",
            assignee="compliance@company.com",
            priority=RiskLevel.HIGH
        )
        
        assert task.id == "task-123"
        assert task.workflow_id == "workflow-123"
        assert task.title == "Review Data Deletion"
        assert task.description == "Review and approve data deletion request"
        assert task.assignee == "compliance@company.com"
        assert task.priority == RiskLevel.HIGH
        assert task.status == WorkflowStatus.PENDING  # Default value
        assert isinstance(task.created_at, datetime)
        assert task.instructions == []  # Default value
        assert task.required_approvals == []  # Default value
    
    def test_human_task_with_details(self):
        """Test HumanTask with detailed instructions and approvals"""
        due_date = datetime.now(timezone.utc)
        
        task = HumanTask(
            id="task-123",
            workflow_id="workflow-123",
            title="Review Data Deletion",
            description="Review and approve data deletion request",
            assignee="compliance@company.com",
            priority=RiskLevel.CRITICAL,
            due_date=due_date,
            instructions=["Check data retention policy", "Verify legal requirements"],
            required_approvals=["legal@company.com", "dpo@company.com"]
        )
        
        assert task.due_date == due_date
        assert len(task.instructions) == 2
        assert "Check data retention policy" in task.instructions
        assert len(task.required_approvals) == 2
        assert "legal@company.com" in task.required_approvals
    
    def test_remediation_metrics_creation(self):
        """Test creating RemediationMetrics"""
        metrics = RemediationMetrics(
            total_violations_processed=100,
            automatic_remediations=60,
            human_loop_remediations=30,
            manual_remediations=10,
            success_rate=0.95,
            average_resolution_time=45.5
        )
        
        assert metrics.total_violations_processed == 100
        assert metrics.automatic_remediations == 60
        assert metrics.human_loop_remediations == 30
        assert metrics.manual_remediations == 10
        assert metrics.success_rate == 0.95
        assert metrics.average_resolution_time == 45.5
        assert metrics.by_risk_level == {}  # Default value
        assert metrics.by_framework == {}  # Default value
    
    def test_remediation_metrics_with_breakdowns(self):
        """Test RemediationMetrics with detailed breakdowns"""
        metrics = RemediationMetrics(
            total_violations_processed=50,
            automatic_remediations=30,
            human_loop_remediations=15,
            manual_remediations=5,
            success_rate=0.90,
            average_resolution_time=35.0,
            by_risk_level={
                RiskLevel.LOW: 20,
                RiskLevel.MEDIUM: 15,
                RiskLevel.HIGH: 10,
                RiskLevel.CRITICAL: 5
            },
            by_framework={
                "GDPR": 25,
                "CCPA": 15,
                "PDPA": 10
            }
        )
        
        assert metrics.by_risk_level[RiskLevel.LOW] == 20
        assert metrics.by_risk_level[RiskLevel.CRITICAL] == 5
        assert metrics.by_framework["GDPR"] == 25
        assert metrics.by_framework["CCPA"] == 15
    
    def test_enums_values(self):
        """Test enum values"""
        # RemediationType
        assert RemediationType.AUTOMATIC == "automatic"
        assert RemediationType.HUMAN_IN_LOOP == "human_in_loop"
        assert RemediationType.MANUAL_ONLY == "manual_only"
        
        # WorkflowStatus
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.IN_PROGRESS == "in_progress"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.CANCELLED == "cancelled"
        assert WorkflowStatus.REQUIRES_HUMAN == "requires_human"
        
        # WorkflowType
        assert WorkflowType.AUTOMATIC == "automatic"
        assert WorkflowType.HUMAN_IN_LOOP == "human_in_loop"
        assert WorkflowType.MANUAL_ONLY == "manual_only"
    
    def test_utc_now_function(self):
        """Test utc_now helper function"""
        now = utc_now()
        assert isinstance(now, datetime)
        assert now.tzinfo == timezone.utc
        
        # Test that it returns current time (within a few seconds)
        import time
        time.sleep(0.1)
        now2 = utc_now()
        assert now2 > now
    
    def test_model_serialization(self):
        """Test model serialization to dict"""
        decision = RemediationDecision(
            violation_id="violation-123",
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.9,
            reasoning="Simple operation",
            estimated_effort=15,
            risk_if_delayed=RiskLevel.LOW,
            prerequisites=["backup_completed"]
        )
        
        data = decision.model_dump()
        assert data["violation_id"] == "violation-123"
        assert data["remediation_type"] == "automatic"
        assert data["confidence_score"] == 0.9
        assert data["prerequisites"] == ["backup_completed"]
    
    def test_model_json_serialization(self):
        """Test model JSON serialization"""
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC
        )
        
        json_str = workflow.model_dump_json()
        assert isinstance(json_str, str)
        assert "workflow-123" in json_str
        assert "automatic" in json_str
        
        # Test deserialization
        import json
        data = json.loads(json_str)
        assert data["id"] == "workflow-123"
        assert data["remediation_type"] == "automatic"