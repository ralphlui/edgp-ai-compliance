"""
Enhanced unit tests for workflow agent with high coverage
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.remediation_agent.agents.workflow_agent import WorkflowAgent
from src.remediation_agent.state.models import (
    RemediationDecision, RemediationWorkflow, WorkflowStep, 
    RemediationType, WorkflowStatus, WorkflowType, HumanTask
)
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation, RiskLevel, DataProcessingActivity, 
    ComplianceFramework, DataType
)


class TestWorkflowAgentEnhanced:
    """Enhanced tests for WorkflowAgent with high coverage"""
    
    @pytest.fixture
    def workflow_agent(self):
        """Create a workflow agent instance"""
        return WorkflowAgent()
    
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
            remediation_actions=["Stop data processing", "Delete personal data", "Send notification"],
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
    def sample_automatic_decision(self, sample_violation, sample_activity):
        """Create a sample automatic remediation decision"""
        return RemediationDecision(
            violation_id=sample_violation.id,
            activity_id=sample_activity.id,
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.9,
            reasoning="Simple data preference update with high confidence",
            estimated_effort=15,
            risk_if_delayed=RiskLevel.LOW,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_human_in_loop_decision(self, sample_violation, sample_activity):
        """Create a sample human-in-loop remediation decision"""
        return RemediationDecision(
            violation_id=sample_violation.id,
            activity_id=sample_activity.id,
            remediation_type=RemediationType.HUMAN_IN_LOOP,
            confidence_score=0.75,
            reasoning="Data deletion requires human oversight",
            estimated_effort=60,
            risk_if_delayed=RiskLevel.MEDIUM,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_manual_decision(self, sample_violation, sample_activity):
        """Create a sample manual-only remediation decision"""
        return RemediationDecision(
            violation_id=sample_violation.id,
            activity_id=sample_activity.id,
            remediation_type=RemediationType.MANUAL_ONLY,
            confidence_score=0.6,
            reasoning="Complex legal changes require manual implementation",
            estimated_effort=480,
            risk_if_delayed=RiskLevel.CRITICAL,
            created_at=datetime.now()
        )
    
    @pytest.mark.asyncio
    async def test_create_workflow_automatic_simple(self, workflow_agent, sample_automatic_decision, sample_violation):
        """Test workflow creation for automatic decision with simple actions"""
        with patch.object(workflow_agent, '_generate_workflow_steps') as mock_steps:
            mock_steps.return_value = [
                WorkflowStep(
                    id="step-1",
                    name="Update User Preference",
                    action_type="api_call",
                    parameters={"endpoint": "/api/users/456/preferences", "method": "PUT"},
                    expected_duration=5
                )
            ]
            
            workflow = await workflow_agent.create_workflow(sample_automatic_decision, sample_violation)
            
            assert isinstance(workflow, RemediationWorkflow)
            assert workflow.violation_id == sample_automatic_decision.violation_id
            assert workflow.activity_id == sample_automatic_decision.activity_id
            assert len(workflow.steps) == 1
            assert workflow.total_estimated_duration == 5
            assert workflow.status == WorkflowStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_create_workflow_human_in_loop_with_approval(self, workflow_agent, sample_human_in_loop_decision, sample_violation):
        """Test workflow creation for human-in-loop decision with approval step"""
        with patch.object(workflow_agent, '_generate_workflow_steps') as mock_steps:
            mock_steps.return_value = [
                WorkflowStep(
                    id="step-1",
                    name="Human Approval Required",
                    action_type="human_approval",
                    parameters={"approval_type": "data_deletion", "approver_role": "data_protection_officer"},
                    expected_duration=30
                ),
                WorkflowStep(
                    id="step-2",
                    name="Delete Personal Data",
                    action_type="database_operation",
                    parameters={"query": "DELETE FROM users WHERE id = 'user-456'"},
                    expected_duration=10
                )
            ]
            
            workflow = await workflow_agent.create_workflow(sample_human_in_loop_decision, sample_violation)
            
            assert len(workflow.steps) == 2
            assert workflow.steps[0].action_type == "human_approval"
            assert workflow.total_estimated_duration == 40
            assert any("approval" in step.name.lower() for step in workflow.steps)
    
    @pytest.mark.asyncio
    async def test_create_workflow_manual_only_human_tasks(self, workflow_agent, sample_manual_decision, sample_violation):
        """Test workflow creation for manual-only decision with human tasks"""
        with patch.object(workflow_agent, '_generate_workflow_steps') as mock_steps:
            mock_steps.return_value = [
                WorkflowStep(
                    id="step-1",
                    name="Legal Review Required",
                    action_type="human_task",
                    parameters={
                        "task_type": "legal_review",
                        "assigned_role": "legal_counsel",
                        "priority": "high"
                    },
                    expected_duration=240
                ),
                WorkflowStep(
                    id="step-2",
                    name="Update Privacy Policy",
                    action_type="human_task",
                    parameters={
                        "task_type": "policy_update",
                        "assigned_role": "compliance_officer"
                    },
                    expected_duration=180
                )
            ]
            
            workflow = await workflow_agent.create_workflow(sample_manual_decision, sample_violation)
            
            assert len(workflow.steps) == 2
            assert all(step.action_type == "human_task" for step in workflow.steps)
            assert workflow.total_estimated_duration == 420
    
    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, workflow_agent):
        """Test successful workflow execution"""
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="API Call",
                    description="Test API call",
                    action_type="api_call",
                    parameters={"endpoint": "/api/test", "method": "GET"}
                )
            ],
            status=WorkflowStatus.PENDING
        )
        
        with patch.object(workflow_agent, '_execute_step') as mock_execute:
            mock_execute.return_value = {"success": True, "message": "Step completed"}
            
            result = await workflow_agent.execute_workflow(workflow)
            
            assert result["success"] is True
            assert result["workflow_id"] == workflow.id
            assert result["execution_status"] == "completed"
            assert len(result["step_results"]) == 1
            mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_failure(self, workflow_agent):
        """Test workflow execution with step failure"""
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="Failing Step",
                    description="Test failing step",
                    action_type="api_call",
                    parameters={"endpoint": "/api/fail"}
                )
            ],
            status=WorkflowStatus.PENDING
        )
        
        with patch.object(workflow_agent, '_execute_step') as mock_execute:
            mock_execute.return_value = {"success": False, "error": "API call failed"}
            
            result = await workflow_agent.execute_workflow(workflow)
            
            assert result["success"] is False
            assert result["execution_status"] == "failed"
            assert "API call failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_workflow_partial_failure(self, workflow_agent):
        """Test workflow execution with partial failure"""
        workflow = RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="Success Step",
                    description="Test success step",
                    action_type="api_call",
                    parameters={"endpoint": "/api/success"}
                ),
                WorkflowStep(
                    id="step-2",
                    name="Fail Step",
                    description="Test fail step",
                    action_type="api_call",
                    parameters={"endpoint": "/api/fail"}
                )
            ],
            status=WorkflowStatus.PENDING
        )
        
        with patch.object(workflow_agent, '_execute_step') as mock_execute:
            mock_execute.side_effect = [
                {"success": True, "message": "Step 1 completed"},
                {"success": False, "error": "Step 2 failed"}
            ]
            
            result = await workflow_agent.execute_workflow(workflow)
            
            assert result["success"] is False
            assert result["execution_status"] == "failed"
            assert len(result["step_results"]) == 2
            assert result["step_results"][0]["success"] is True
            assert result["step_results"][1]["success"] is False
    
    @pytest.mark.asyncio
    async def test_execute_step_api_call_success(self, workflow_agent):
        """Test successful API call step execution"""
        step = WorkflowStep(
            id="step-1",
            name="API Call",
            action_type="api_call",
            parameters={
                "endpoint": "/api/users/123/preferences",
                "method": "PUT",
                "data": {"preference": "updated"}
            },
            expected_duration=5
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is True
            assert "API call completed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_step_api_call_failure(self, workflow_agent):
        """Test failed API call step execution"""
        step = WorkflowStep(
            id="step-1",
            name="API Call",
            action_type="api_call",
            parameters={"endpoint": "/api/fail", "method": "POST"},
            expected_duration=5
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text.return_value = "Internal Server Error"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is False
            assert "API call failed" in result["error"]
            assert "500" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_step_database_operation_success(self, workflow_agent):
        """Test successful database operation step execution"""
        step = WorkflowStep(
            id="step-1",
            name="Database Operation",
            action_type="database_operation",
            parameters={
                "query": "UPDATE users SET consent_status = 'withdrawn' WHERE id = ?",
                "params": ["user-123"]
            },
            expected_duration=10
        )
        
        with patch.object(workflow_agent, '_execute_database_query') as mock_db:
            mock_db.return_value = {"rows_affected": 1, "success": True}
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is True
            assert "Database operation completed" in result["message"]
            mock_db.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_step_database_operation_failure(self, workflow_agent):
        """Test failed database operation step execution"""
        step = WorkflowStep(
            id="step-1",
            name="Database Operation",
            action_type="database_operation",
            parameters={"query": "INVALID SQL QUERY"},
            expected_duration=10
        )
        
        with patch.object(workflow_agent, '_execute_database_query') as mock_db:
            mock_db.side_effect = Exception("SQL syntax error")
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is False
            assert "Database operation failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_step_email_notification_success(self, workflow_agent):
        """Test successful email notification step execution"""
        step = WorkflowStep(
            id="step-1",
            name="Send Email",
            action_type="email_notification",
            parameters={
                "recipient": "user@example.com",
                "subject": "Data Processing Update",
                "template": "data_update_notification",
                "data": {"user_id": "123"}
            },
            expected_duration=3
        )
        
        with patch.object(workflow_agent, '_send_email') as mock_email:
            mock_email.return_value = {"message_id": "msg-123", "success": True}
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is True
            assert "Email notification sent" in result["message"]
            mock_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_step_human_approval_creation(self, workflow_agent):
        """Test human approval step execution (creates approval task)"""
        step = WorkflowStep(
            id="step-1",
            name="Human Approval Required",
            action_type="human_approval",
            parameters={
                "approval_type": "data_deletion",
                "approver_role": "data_protection_officer",
                "description": "Approve deletion of user personal data"
            },
            expected_duration=30
        )
        
        with patch.object(workflow_agent, '_create_approval_task') as mock_approval:
            mock_approval.return_value = {"task_id": "task-123", "status": "pending"}
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is True
            assert "Approval task created" in result["message"]
            assert result["task_id"] == "task-123"
    
    @pytest.mark.asyncio
    async def test_execute_step_human_task_creation(self, workflow_agent):
        """Test human task step execution (creates manual task)"""
        step = WorkflowStep(
            id="step-1",
            name="Legal Review",
            action_type="human_task",
            parameters={
                "task_type": "legal_review",
                "assigned_role": "legal_counsel",
                "description": "Review compliance implications",
                "priority": "high"
            },
            expected_duration=120
        )
        
        with patch.object(workflow_agent, '_create_human_task') as mock_task:
            mock_task.return_value = {"task_id": "task-456", "status": "assigned"}
            
            result = await workflow_agent._execute_step(step)
            
            assert result["success"] is True
            assert "Human task created" in result["message"]
            assert result["task_id"] == "task-456"
    
    @pytest.mark.asyncio
    async def test_execute_step_unsupported_action(self, workflow_agent):
        """Test execution of step with unsupported action type"""
        step = WorkflowStep(
            id="step-1",
            name="Unknown Action",
            action_type="unknown_action",
            parameters={"param": "value"},
            expected_duration=10
        )
        
        result = await workflow_agent._execute_step(step)
        
        assert result["success"] is False
        assert "Unsupported action type" in result["error"]
    
    def test_generate_workflow_steps_automatic_simple(self, workflow_agent, sample_automatic_decision, sample_violation):
        """Test workflow step generation for simple automatic decision"""
        sample_violation.remediation_actions = ["Update user preference setting"]
        
        steps = workflow_agent._generate_workflow_steps(sample_automatic_decision, sample_violation)
        
        assert len(steps) >= 1
        assert steps[0].action_type in ["api_call", "database_operation"]
        assert "update" in steps[0].name.lower() or "preference" in steps[0].name.lower()
    
    def test_generate_workflow_steps_data_deletion(self, workflow_agent, sample_human_in_loop_decision, sample_violation):
        """Test workflow step generation for data deletion"""
        sample_violation.remediation_actions = ["Delete personal data", "Send deletion confirmation"]
        
        steps = workflow_agent._generate_workflow_steps(sample_human_in_loop_decision, sample_violation)
        
        assert len(steps) >= 2
        # Should include approval step for human-in-loop
        assert any(step.action_type == "human_approval" for step in steps)
        # Should include deletion step
        assert any("delete" in step.name.lower() for step in steps)
    
    def test_generate_workflow_steps_manual_only_complex(self, workflow_agent, sample_manual_decision, sample_violation):
        """Test workflow step generation for complex manual-only decision"""
        sample_violation.remediation_actions = [
            "Conduct legal review",
            "Update privacy policy",
            "Implement new consent mechanism",
            "Notify regulatory authorities"
        ]
        
        steps = workflow_agent._generate_workflow_steps(sample_manual_decision, sample_violation)
        
        assert len(steps) >= 3
        # All steps should be human tasks for manual-only
        assert all(step.action_type == "human_task" for step in steps)
        # Should cover different aspects
        task_types = [step.parameters.get("task_type", "") for step in steps]
        assert len(set(task_types)) >= 3  # Different task types
    
    def test_map_remediation_action_to_step_update_preference(self, workflow_agent):
        """Test mapping remediation action to workflow step for preference update"""
        action = "Update user preference setting"
        decision_type = RemediationType.AUTOMATIC
        
        step = workflow_agent._map_remediation_action_to_step(action, 1, decision_type)
        
        assert step.action_type == "api_call"
        assert "update" in step.name.lower()
        assert "preference" in step.name.lower()
        assert "endpoint" in step.parameters
    
    def test_map_remediation_action_to_step_delete_data(self, workflow_agent):
        """Test mapping remediation action to workflow step for data deletion"""
        action = "Delete personal data"
        decision_type = RemediationType.HUMAN_IN_LOOP
        
        step = workflow_agent._map_remediation_action_to_step(action, 1, decision_type)
        
        assert step.action_type == "database_operation"
        assert "delete" in step.name.lower()
        assert "query" in step.parameters
    
    def test_map_remediation_action_to_step_send_notification(self, workflow_agent):
        """Test mapping remediation action to workflow step for notification"""
        action = "Send notification to user"
        decision_type = RemediationType.AUTOMATIC
        
        step = workflow_agent._map_remediation_action_to_step(action, 1, decision_type)
        
        assert step.action_type == "email_notification"
        assert "notification" in step.name.lower() or "email" in step.name.lower()
        assert "recipient" in step.parameters
    
    def test_map_remediation_action_to_step_legal_review(self, workflow_agent):
        """Test mapping remediation action to workflow step for legal review"""
        action = "Conduct legal review"
        decision_type = RemediationType.MANUAL_ONLY
        
        step = workflow_agent._map_remediation_action_to_step(action, 1, decision_type)
        
        assert step.action_type == "human_task"
        assert "legal" in step.name.lower()
        assert step.parameters["task_type"] == "legal_review"
        assert step.parameters["assigned_role"] == "legal_counsel"
    
    def test_map_remediation_action_to_step_generic_action(self, workflow_agent):
        """Test mapping generic remediation action to workflow step"""
        action = "Perform custom compliance action"
        decision_type = RemediationType.HUMAN_IN_LOOP
        
        step = workflow_agent._map_remediation_action_to_step(action, 1, decision_type)
        
        # Should create appropriate step based on decision type
        if decision_type == RemediationType.AUTOMATIC:
            assert step.action_type in ["api_call", "database_operation"]
        else:
            assert step.action_type in ["human_task", "human_approval"]
    
    def test_estimate_step_duration_api_call(self, workflow_agent):
        """Test step duration estimation for API call"""
        action = "Update user preference via API"
        action_type = "api_call"
        
        duration = workflow_agent._estimate_step_duration(action, action_type)
        
        assert 1 <= duration <= 15  # API calls should be quick
    
    def test_estimate_step_duration_database_operation(self, workflow_agent):
        """Test step duration estimation for database operation"""
        action = "Delete records from database"
        action_type = "database_operation"
        
        duration = workflow_agent._estimate_step_duration(action, action_type)
        
        assert 2 <= duration <= 30  # Database ops can vary
    
    def test_estimate_step_duration_human_task(self, workflow_agent):
        """Test step duration estimation for human task"""
        action = "Conduct legal review of policy changes"
        action_type = "human_task"
        
        duration = workflow_agent._estimate_step_duration(action, action_type)
        
        assert 30 <= duration <= 480  # Human tasks take longer
    
    def test_estimate_step_duration_complex_action(self, workflow_agent):
        """Test step duration estimation for complex action"""
        action = "Implement comprehensive new consent management system with database migration"
        action_type = "human_task"
        
        duration = workflow_agent._estimate_step_duration(action, action_type)
        
        assert duration >= 120  # Complex actions take much longer
    
    def test_determine_action_type_update_keywords(self, workflow_agent):
        """Test action type determination for update-related actions"""
        assert workflow_agent._determine_action_type("Update user preferences", RemediationType.AUTOMATIC) == "api_call"
        assert workflow_agent._determine_action_type("Modify settings", RemediationType.AUTOMATIC) == "api_call"
        assert workflow_agent._determine_action_type("Change configuration", RemediationType.AUTOMATIC) == "api_call"
    
    def test_determine_action_type_delete_keywords(self, workflow_agent):
        """Test action type determination for delete-related actions"""
        assert workflow_agent._determine_action_type("Delete personal data", RemediationType.AUTOMATIC) == "database_operation"
        assert workflow_agent._determine_action_type("Remove user records", RemediationType.HUMAN_IN_LOOP) == "database_operation"
        assert workflow_agent._determine_action_type("Purge old data", RemediationType.AUTOMATIC) == "database_operation"
    
    def test_determine_action_type_notification_keywords(self, workflow_agent):
        """Test action type determination for notification-related actions"""
        assert workflow_agent._determine_action_type("Send notification", RemediationType.AUTOMATIC) == "email_notification"
        assert workflow_agent._determine_action_type("Email user", RemediationType.HUMAN_IN_LOOP) == "email_notification"
        assert workflow_agent._determine_action_type("Notify data subject", RemediationType.AUTOMATIC) == "email_notification"
    
    def test_determine_action_type_review_keywords_manual(self, workflow_agent):
        """Test action type determination for review-related actions in manual context"""
        assert workflow_agent._determine_action_type("Conduct legal review", RemediationType.MANUAL_ONLY) == "human_task"
        assert workflow_agent._determine_action_type("Review compliance implications", RemediationType.MANUAL_ONLY) == "human_task"
        assert workflow_agent._determine_action_type("Analyze policy impact", RemediationType.MANUAL_ONLY) == "human_task"
    
    def test_determine_action_type_approval_needed(self, workflow_agent):
        """Test action type determination for actions requiring approval"""
        assert workflow_agent._determine_action_type("Delete sensitive data", RemediationType.HUMAN_IN_LOOP) == "human_approval"
        assert workflow_agent._determine_action_type("Modify privacy policy", RemediationType.HUMAN_IN_LOOP) == "human_approval"
        assert workflow_agent._determine_action_type("Change data retention", RemediationType.HUMAN_IN_LOOP) == "human_approval"
    
    def test_create_api_call_parameters_update(self, workflow_agent):
        """Test API call parameter creation for update actions"""
        action = "Update user consent preferences"
        violation_id = "violation-123"
        
        params = workflow_agent._create_api_call_parameters(action, violation_id)
        
        assert "endpoint" in params
        assert "method" in params
        assert params["method"] in ["PUT", "PATCH", "POST"]
        assert "data" in params
    
    def test_create_api_call_parameters_stop_processing(self, workflow_agent):
        """Test API call parameter creation for stop processing actions"""
        action = "Stop data processing activity"
        violation_id = "violation-123"
        
        params = workflow_agent._create_api_call_parameters(action, violation_id)
        
        assert "endpoint" in params
        assert "stop" in params["endpoint"] or "halt" in params["endpoint"]
        assert params["method"] == "POST"
    
    def test_create_database_parameters_delete(self, workflow_agent):
        """Test database parameter creation for delete operations"""
        action = "Delete user personal data"
        violation_id = "violation-123"
        
        params = workflow_agent._create_database_parameters(action, violation_id)
        
        assert "query" in params
        assert "DELETE" in params["query"].upper()
        assert "backup_required" in params
        assert params["backup_required"] is True
    
    def test_create_database_parameters_update(self, workflow_agent):
        """Test database parameter creation for update operations"""
        action = "Update consent status in database"
        violation_id = "violation-123"
        
        params = workflow_agent._create_database_parameters(action, violation_id)
        
        assert "query" in params
        assert "UPDATE" in params["query"].upper()
        assert "params" in params
    
    def test_create_email_parameters_notification(self, workflow_agent):
        """Test email parameter creation for notifications"""
        action = "Send data processing notification to user"
        violation_id = "violation-123"
        
        params = workflow_agent._create_email_parameters(action, violation_id)
        
        assert "recipient" in params
        assert "subject" in params
        assert "template" in params
        assert "data" in params
        assert params["data"]["violation_id"] == violation_id
    
    def test_create_email_parameters_deletion_confirmation(self, workflow_agent):
        """Test email parameter creation for deletion confirmation"""
        action = "Send deletion confirmation email"
        violation_id = "violation-123"
        
        params = workflow_agent._create_email_parameters(action, violation_id)
        
        assert "template" in params
        assert "deletion" in params["template"] or "confirm" in params["template"]
        assert "subject" in params
        assert "deletion" in params["subject"].lower() or "confirm" in params["subject"].lower()
    
    def test_create_human_task_parameters_legal_review(self, workflow_agent):
        """Test human task parameter creation for legal review"""
        action = "Conduct comprehensive legal review"
        violation_id = "violation-123"
        
        params = workflow_agent._create_human_task_parameters(action, violation_id)
        
        assert params["task_type"] == "legal_review"
        assert params["assigned_role"] == "legal_counsel"
        assert params["priority"] == "high"
        assert params["description"] == action
    
    def test_create_human_task_parameters_policy_update(self, workflow_agent):
        """Test human task parameter creation for policy update"""
        action = "Update privacy policy documents"
        violation_id = "violation-123"
        
        params = workflow_agent._create_human_task_parameters(action, violation_id)
        
        assert params["task_type"] == "policy_update"
        assert params["assigned_role"] == "compliance_officer"
        assert "update" in params["description"].lower()
    
    def test_create_approval_parameters_data_deletion(self, workflow_agent):
        """Test approval parameter creation for data deletion"""
        action = "Delete sensitive user data"
        violation_id = "violation-123"
        
        params = workflow_agent._create_approval_parameters(action, violation_id)
        
        assert params["approval_type"] == "data_deletion"
        assert params["approver_role"] == "data_protection_officer"
        assert params["description"] == action
        assert params["requires_documentation"] is True
    
    def test_create_approval_parameters_policy_change(self, workflow_agent):
        """Test approval parameter creation for policy changes"""
        action = "Modify data retention policy"
        violation_id = "violation-123"
        
        params = workflow_agent._create_approval_parameters(action, violation_id)
        
        assert params["approval_type"] == "policy_change"
        assert params["approver_role"] in ["compliance_officer", "data_protection_officer"]
        assert params["requires_legal_review"] is True
    
    def test_add_approval_step_for_human_in_loop(self, workflow_agent):
        """Test adding approval step for human-in-loop decisions"""
        steps = [
            WorkflowStep(
                id="step-1",
                name="Delete Data",
                action_type="database_operation",
                parameters={"query": "DELETE FROM users"},
                expected_duration=10
            )
        ]
        violation_id = "violation-123"
        
        updated_steps = workflow_agent._add_approval_step_if_needed(steps, RemediationType.HUMAN_IN_LOOP, violation_id)
        
        assert len(updated_steps) == 2
        assert updated_steps[0].action_type == "human_approval"
        assert updated_steps[1].action_type == "database_operation"
    
    def test_no_approval_step_for_automatic(self, workflow_agent):
        """Test no approval step added for automatic decisions"""
        steps = [
            WorkflowStep(
                id="step-1",
                name="Update Preference",
                action_type="api_call",
                parameters={"endpoint": "/api/update"},
                expected_duration=5
            )
        ]
        violation_id = "violation-123"
        
        updated_steps = workflow_agent._add_approval_step_if_needed(steps, RemediationType.AUTOMATIC, violation_id)
        
        assert len(updated_steps) == 1
        assert updated_steps[0].action_type == "api_call"
    
    def test_calculate_total_duration(self, workflow_agent):
        """Test total duration calculation"""
        steps = [
            WorkflowStep(id="1", name="Step 1", action_type="api_call", parameters={}, expected_duration=10),
            WorkflowStep(id="2", name="Step 2", action_type="database_operation", parameters={}, expected_duration=15),
            WorkflowStep(id="3", name="Step 3", action_type="email_notification", parameters={}, expected_duration=5)
        ]
        
        total = workflow_agent._calculate_total_duration(steps)
        
        assert total == 30
    
    def test_calculate_total_duration_empty_steps(self, workflow_agent):
        """Test total duration calculation with empty steps"""
        total = workflow_agent._calculate_total_duration([])
        
        assert total == 0
    
    @pytest.mark.asyncio
    async def test_create_approval_task(self, workflow_agent):
        """Test approval task creation"""
        params = {
            "approval_type": "data_deletion",
            "approver_role": "data_protection_officer",
            "description": "Approve deletion of user data",
            "violation_id": "violation-123"
        }
        
        with patch.object(workflow_agent, '_store_human_task') as mock_store:
            mock_store.return_value = {"task_id": "approval-123", "status": "pending"}
            
            result = await workflow_agent._create_approval_task(params)
            
            assert result["task_id"] == "approval-123"
            assert result["status"] == "pending"
            mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_human_task(self, workflow_agent):
        """Test human task creation"""
        params = {
            "task_type": "legal_review",
            "assigned_role": "legal_counsel",
            "description": "Review compliance implications",
            "priority": "high"
        }
        
        with patch.object(workflow_agent, '_store_human_task') as mock_store:
            mock_store.return_value = {"task_id": "task-456", "status": "assigned"}
            
            result = await workflow_agent._create_human_task(params)
            
            assert result["task_id"] == "task-456"
            assert result["status"] == "assigned"
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, workflow_agent):
        """Test successful email sending"""
        params = {
            "recipient": "user@example.com",
            "subject": "Test Email",
            "template": "test_template",
            "data": {"key": "value"}
        }
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            result = await workflow_agent._send_email(params)
            
            assert result["success"] is True
            assert "message_id" in result
    
    @pytest.mark.asyncio
    async def test_execute_database_query_success(self, workflow_agent):
        """Test successful database query execution"""
        query = "UPDATE users SET status = ? WHERE id = ?"
        params = ["inactive", "user-123"]
        
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value.__enter__.return_value = mock_conn
            
            result = await workflow_agent._execute_database_query(query, params)
            
            assert result["success"] is True
            assert result["rows_affected"] == 1


class TestWorkflowAgentEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def workflow_agent(self):
        return WorkflowAgent()
    
    @pytest.mark.asyncio
    async def test_create_workflow_empty_actions(self, workflow_agent, sample_automatic_decision, sample_violation):
        """Test workflow creation with empty remediation actions"""
        sample_violation.remediation_actions = []
        
        workflow = await workflow_agent.create_workflow(sample_automatic_decision, sample_violation)
        
        # Should create minimal workflow or default steps
        assert isinstance(workflow, RemediationWorkflow)
        assert len(workflow.steps) >= 1  # Should have at least a default step
    
    @pytest.mark.asyncio
    async def test_create_workflow_none_actions(self, workflow_agent, sample_automatic_decision, sample_violation):
        """Test workflow creation with None remediation actions"""
        sample_violation.remediation_actions = None
        
        workflow = await workflow_agent.create_workflow(sample_automatic_decision, sample_violation)
        
        assert isinstance(workflow, RemediationWorkflow)
        assert len(workflow.steps) >= 1
    
    @pytest.mark.asyncio
    async def test_execute_workflow_empty_steps(self, workflow_agent):
        """Test execution of workflow with no steps"""
        workflow = RemediationWorkflow(
            id="empty-workflow",
            violation_id="violation-123",
            activity_id="activity-123",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[],
            status=WorkflowStatus.PENDING
        )
        
        result = await workflow_agent.execute_workflow(workflow)
        
        assert result["success"] is True  # Empty workflow succeeds trivially
        assert result["execution_status"] == "completed"
        assert len(result["step_results"]) == 0
    
    def test_estimate_step_duration_empty_action(self, workflow_agent):
        """Test step duration estimation with empty action"""
        duration = workflow_agent._estimate_step_duration("", "api_call")
        
        assert duration > 0  # Should provide reasonable default
    
    def test_determine_action_type_unknown_action(self, workflow_agent):
        """Test action type determination for unknown action"""
        action_type = workflow_agent._determine_action_type("Unknown mysterious action", RemediationType.AUTOMATIC)
        
        assert action_type in ["api_call", "database_operation", "human_task"]  # Should provide reasonable default
    
    def test_calculate_total_duration_none_durations(self, workflow_agent):
        """Test total duration calculation with None durations"""
        steps = [
            WorkflowStep(id="1", name="Step 1", action_type="api_call", parameters={}, expected_duration=None)
        ]
        
        total = workflow_agent._calculate_total_duration(steps)
        
        assert total >= 0  # Should handle gracefully