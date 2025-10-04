"""
Unit tests for LangGraph workflow orchestration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime

from src.remediation_agent.graphs.remediation_graph import RemediationGraph
from src.remediation_agent.state.models import (
    RemediationSignal,
    RemediationDecision,
    RemediationWorkflow,
    WorkflowStep,
    WorkflowStatus
)
from src.remediation_agent.state.remediation_state import RemediationState
from src.compliance_agent.models.compliance_models import RiskLevel


class TestRemediationGraph:
    """Test RemediationGraph class and workflow orchestration"""
    
    @pytest.fixture
    def remediation_graph(self):
        """Create a remediation graph instance for testing"""
        return RemediationGraph()
    
    @pytest.fixture
    def sample_state(self, sample_remediation_signal):
        """Create a sample remediation state for testing"""
        return RemediationState(
            remediation_signal=sample_remediation_signal,
            decision=None,
            workflow=None,
            current_step=0,
            step_results=[],
            validation_results={},
            notifications_sent=[],
            errors=[],
            metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_build_graph_structure(self, remediation_graph):
        """Test that the graph is built with correct structure"""
        graph = remediation_graph.build_graph()
        
        # Verify graph has expected nodes
        expected_nodes = [
            "decision_node",
            "validation_node", 
            "workflow_node",
            "execution_node",
            "notification_node",
            "completion_node"
        ]
        
        # Check that graph contains expected components
        assert graph is not None
        # Note: Specific assertions depend on LangGraph implementation details
    
    @pytest.mark.asyncio
    async def test_process_remediation_signal_automatic_flow(self, remediation_graph, sample_state):
        """Test processing of remediation signal through automatic flow"""
        # Setup automatic decision
        sample_state.remediation_signal.violation.risk_level = RiskLevel.LOW
        sample_state.remediation_signal.violation.remediation_actions = [
            "Update user email preference"
        ]
        
        with patch.object(remediation_graph, 'decision_agent') as mock_decision, \
             patch.object(remediation_graph, 'validation_agent') as mock_validation, \
             patch.object(remediation_graph, 'workflow_agent') as mock_workflow:
            
            # Mock agent responses
            mock_decision.make_decision.return_value = RemediationDecision(
                decision_type="automatic",
                auto_approve=True,
                rationale="Low risk operation"
            )
            
            mock_validation.assess_feasibility.return_value = {
                "feasible": True,
                "overall_feasibility_score": 0.9,
                "automation_recommendation": "automatic"
            }
            
            mock_workflow.orchestrate_remediation.return_value = {
                "workflow_created": True,
                "workflow_id": "workflow-123",
                "steps": [{"action": "Update user email preference"}]
            }
            
            result = await remediation_graph.process_remediation_signal(sample_state.remediation_signal)
            
            assert result["success"] is True
            assert result["decision"]["decision_type"] == "automatic"
            assert result["workflow_created"] is True
    
    @pytest.mark.asyncio
    async def test_process_remediation_signal_human_in_loop_flow(self, remediation_graph, sample_state):
        """Test processing through human-in-the-loop flow"""
        # Setup human-in-loop scenario
        sample_state.remediation_signal.violation.risk_level = RiskLevel.MEDIUM
        sample_state.remediation_signal.violation.remediation_actions = [
            "Delete user personal data"
        ]
        
        with patch.object(remediation_graph, 'decision_agent') as mock_decision, \
             patch.object(remediation_graph, 'validation_agent') as mock_validation:
            
            mock_decision.make_decision.return_value = RemediationDecision(
                decision_type="human_in_loop",
                auto_approve=False,
                rationale="Data deletion requires human oversight"
            )
            
            mock_validation.assess_feasibility.return_value = {
                "feasible": True,
                "overall_feasibility_score": 0.6,
                "automation_recommendation": "human_in_loop"
            }
            
            result = await remediation_graph.process_remediation_signal(sample_state.remediation_signal)
            
            assert result["success"] is True
            assert result["decision"]["decision_type"] == "human_in_loop"
            assert result["requires_approval"] is True
    
    @pytest.mark.asyncio
    async def test_process_remediation_signal_manual_only_flow(self, remediation_graph, sample_state):
        """Test processing through manual-only flow"""
        # Setup manual-only scenario
        sample_state.remediation_signal.violation.risk_level = RiskLevel.CRITICAL
        sample_state.remediation_signal.violation.remediation_actions = [
            "Conduct legal review of data processing agreements"
        ]
        
        with patch.object(remediation_graph, 'decision_agent') as mock_decision:
            mock_decision.make_decision.return_value = RemediationDecision(
                decision_type="manual_only",
                auto_approve=False,
                rationale="Critical legal operation requires manual handling"
            )
            
            result = await remediation_graph.process_remediation_signal(sample_state.remediation_signal)
            
            assert result["success"] is True
            assert result["decision"]["decision_type"] == "manual_only"
            assert result["requires_manual_execution"] is True
    
    @pytest.mark.asyncio
    async def test_decision_node_processing(self, remediation_graph, sample_state):
        """Test decision node processing"""
        with patch.object(remediation_graph, 'decision_agent') as mock_decision:
            mock_decision.make_decision.return_value = RemediationDecision(
                decision_type="automatic",
                auto_approve=True,
                rationale="Simple operation"
            )
            
            updated_state = await remediation_graph._decision_node(sample_state)
            
            assert updated_state.decision is not None
            assert updated_state.decision.decision_type == "automatic"
            assert updated_state.decision.auto_approve is True
    
    @pytest.mark.asyncio
    async def test_validation_node_processing(self, remediation_graph, sample_state):
        """Test validation node processing"""
        # Add decision to state
        sample_state.decision = RemediationDecision(
            decision_type="automatic",
            auto_approve=True,
            rationale="Test decision"
        )
        
        with patch.object(remediation_graph, 'validation_agent') as mock_validation:
            mock_validation.assess_feasibility.return_value = {
                "feasible": True,
                "overall_feasibility_score": 0.85,
                "automation_recommendation": "automatic",
                "blockers": [],
                "prerequisites": []
            }
            
            updated_state = await remediation_graph._validation_node(sample_state)
            
            assert "feasibility" in updated_state.validation_results
            assert updated_state.validation_results["feasibility"]["feasible"] is True
    
    @pytest.mark.asyncio
    async def test_workflow_node_processing(self, remediation_graph, sample_state):
        """Test workflow node processing"""
        # Setup state with decision and validation
        sample_state.decision = RemediationDecision(
            decision_type="automatic",
            auto_approve=True,
            rationale="Test decision"
        )
        sample_state.validation_results = {
            "feasibility": {"feasible": True, "overall_feasibility_score": 0.9}
        }
        
        with patch.object(remediation_graph, 'workflow_agent') as mock_workflow:
            mock_workflow.orchestrate_remediation.return_value = {
                "workflow_created": True,
                "workflow_id": "workflow-123",
                "steps": [
                    {"action": "Update user preference", "order": 0}
                ],
                "status": "initiated"
            }
            
            updated_state = await remediation_graph._workflow_node(sample_state)
            
            assert updated_state.workflow is not None
            assert updated_state.workflow.workflow_id == "workflow-123"
    
    @pytest.mark.asyncio
    async def test_execution_node_processing(self, remediation_graph, sample_state, sample_workflow_steps):
        """Test execution node processing"""
        # Setup state with workflow
        sample_state.workflow = RemediationWorkflow(
            workflow_id="workflow-123",
            remediation_signal_id=sample_state.remediation_signal.violation.id,
            steps=sample_workflow_steps,
            status="initiated"
        )
        
        with patch.object(remediation_graph, 'sqs_tool') as mock_sqs, \
             patch.object(remediation_graph, 'remediation_validator') as mock_validator:
            
            mock_validator.validate_remediation_step.return_value = {
                "valid": True,
                "validation_score": 0.9,
                "errors": []
            }
            
            mock_sqs.send_remediation_signal.return_value = {
                "success": True,
                "message_id": "msg-123"
            }
            
            updated_state = await remediation_graph._execution_node(sample_state)
            
            assert len(updated_state.step_results) > 0
            assert updated_state.current_step > 0
    
    @pytest.mark.asyncio
    async def test_notification_node_processing(self, remediation_graph, sample_state):
        """Test notification node processing"""
        # Setup state with completed workflow
        sample_state.workflow = RemediationWorkflow(
            workflow_id="workflow-123",
            remediation_signal_id=sample_state.remediation_signal.violation.id,
            steps=[],
            status="completed"
        )
        
        with patch.object(remediation_graph, 'notification_tool') as mock_notification:
            mock_notification.send_workflow_completed_notification.return_value = {
                "success": True,
                "notifications_sent": ["email", "slack"]
            }
            
            updated_state = await remediation_graph._notification_node(sample_state)
            
            assert len(updated_state.notifications_sent) > 0
    
    @pytest.mark.asyncio
    async def test_conditional_routing_automatic_to_validation(self, remediation_graph, sample_state):
        """Test conditional routing from decision to validation for automatic flow"""
        sample_state.decision = RemediationDecision(
            decision_type="automatic",
            auto_approve=True,
            rationale="Automatic decision"
        )
        
        next_node = remediation_graph._route_after_decision(sample_state)
        
        assert next_node == "validation_node"
    
    @pytest.mark.asyncio
    async def test_conditional_routing_manual_to_notification(self, remediation_graph, sample_state):
        """Test conditional routing from decision to notification for manual flow"""
        sample_state.decision = RemediationDecision(
            decision_type="manual_only",
            auto_approve=False,
            rationale="Manual decision"
        )
        
        next_node = remediation_graph._route_after_decision(sample_state)
        
        assert next_node == "notification_node"
    
    @pytest.mark.asyncio
    async def test_conditional_routing_validation_to_workflow(self, remediation_graph, sample_state):
        """Test conditional routing from validation to workflow when feasible"""
        sample_state.validation_results = {
            "feasibility": {"feasible": True, "overall_feasibility_score": 0.8}
        }
        
        next_node = remediation_graph._route_after_validation(sample_state)
        
        assert next_node == "workflow_node"
    
    @pytest.mark.asyncio
    async def test_conditional_routing_validation_to_notification_not_feasible(self, remediation_graph, sample_state):
        """Test conditional routing from validation to notification when not feasible"""
        sample_state.validation_results = {
            "feasibility": {"feasible": False, "overall_feasibility_score": 0.3}
        }
        
        next_node = remediation_graph._route_after_validation(sample_state)
        
        assert next_node == "notification_node"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_decision_node(self, remediation_graph, sample_state):
        """Test error handling in decision node"""
        with patch.object(remediation_graph, 'decision_agent') as mock_decision:
            mock_decision.make_decision.side_effect = Exception("Decision agent error")
            
            updated_state = await remediation_graph._decision_node(sample_state)
            
            assert len(updated_state.errors) > 0
            assert "Decision agent error" in str(updated_state.errors)
    
    @pytest.mark.asyncio
    async def test_error_handling_in_validation_node(self, remediation_graph, sample_state):
        """Test error handling in validation node"""
        sample_state.decision = RemediationDecision(
            decision_type="automatic",
            auto_approve=True,
            rationale="Test"
        )
        
        with patch.object(remediation_graph, 'validation_agent') as mock_validation:
            mock_validation.assess_feasibility.side_effect = Exception("Validation error")
            
            updated_state = await remediation_graph._validation_node(sample_state)
            
            assert len(updated_state.errors) > 0
            assert "Validation error" in str(updated_state.errors)
    
    @pytest.mark.asyncio
    async def test_state_persistence_and_checkpointing(self, remediation_graph, sample_state):
        """Test state persistence and checkpointing functionality"""
        with patch.object(remediation_graph, '_save_checkpoint') as mock_save:
            mock_save.return_value = {"checkpoint_id": "checkpoint-123"}
            
            checkpoint_result = await remediation_graph._save_checkpoint(sample_state)
            
            assert checkpoint_result["checkpoint_id"] is not None
            mock_save.assert_called_once_with(sample_state)
    
    @pytest.mark.asyncio
    async def test_state_restoration_from_checkpoint(self, remediation_graph):
        """Test state restoration from checkpoint"""
        checkpoint_id = "checkpoint-123"
        
        with patch.object(remediation_graph, '_load_checkpoint') as mock_load:
            mock_load.return_value = RemediationState(
                remediation_signal=MagicMock(),
                decision=None,
                workflow=None,
                current_step=0,
                step_results=[],
                validation_results={},
                notifications_sent=[],
                errors=[],
                metadata={"checkpoint_id": checkpoint_id}
            )
            
            restored_state = await remediation_graph._load_checkpoint(checkpoint_id)
            
            assert restored_state is not None
            assert restored_state.metadata["checkpoint_id"] == checkpoint_id
    
    @pytest.mark.asyncio
    async def test_workflow_execution_with_multiple_steps(self, remediation_graph, sample_state):
        """Test workflow execution with multiple steps"""
        # Setup workflow with multiple steps
        steps = [
            WorkflowStep(
                action="Backup user data",
                step_type="automated",
                order=0,
                estimated_duration_minutes=5
            ),
            WorkflowStep(
                action="Delete user data",
                step_type="automated_with_approval",
                order=1,
                estimated_duration_minutes=10
            ),
            WorkflowStep(
                action="Send confirmation email",
                step_type="automated",
                order=2,
                estimated_duration_minutes=2
            )
        ]
        
        sample_state.workflow = RemediationWorkflow(
            workflow_id="workflow-123",
            remediation_signal_id=sample_state.remediation_signal.violation.id,
            steps=steps,
            status="initiated"
        )
        
        with patch.object(remediation_graph, 'remediation_validator') as mock_validator, \
             patch.object(remediation_graph, 'sqs_tool') as mock_sqs:
            
            mock_validator.validate_remediation_step.return_value = {
                "valid": True,
                "validation_score": 0.9,
                "errors": []
            }
            
            mock_sqs.send_remediation_signal.return_value = {
                "success": True,
                "message_id": "msg-123"
            }
            
            # Execute multiple steps
            for _ in range(len(steps)):
                updated_state = await remediation_graph._execution_node(sample_state)
                sample_state = updated_state
            
            assert sample_state.current_step == len(steps)
            assert len(sample_state.step_results) == len(steps)
    
    @pytest.mark.asyncio
    async def test_parallel_step_execution_capability(self, remediation_graph, sample_state):
        """Test capability for parallel step execution"""
        # Setup workflow with parallel-capable steps
        parallel_steps = [
            WorkflowStep(
                action="Update user email preference",
                step_type="automated",
                order=0,
                can_execute_in_parallel=True
            ),
            WorkflowStep(
                action="Update user phone preference", 
                step_type="automated",
                order=0,  # Same order indicates parallel execution
                can_execute_in_parallel=True
            )
        ]
        
        sample_state.workflow = RemediationWorkflow(
            workflow_id="workflow-123",
            remediation_signal_id=sample_state.remediation_signal.violation.id,
            steps=parallel_steps,
            status="initiated"
        )
        
        parallel_capability = remediation_graph._can_execute_steps_in_parallel(parallel_steps)
        
        assert parallel_capability is True
    
    def test_graph_configuration_and_setup(self, remediation_graph):
        """Test graph configuration and setup"""
        assert remediation_graph.config is not None
        assert hasattr(remediation_graph, 'decision_agent')
        assert hasattr(remediation_graph, 'validation_agent')
        assert hasattr(remediation_graph, 'workflow_agent')
        assert hasattr(remediation_graph, 'sqs_tool')
        assert hasattr(remediation_graph, 'notification_tool')
        assert hasattr(remediation_graph, 'remediation_validator')
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow_execution(self, remediation_graph, sample_remediation_signal):
        """Test complete end-to-end workflow execution"""
        # This is an integration-style test for the complete flow
        with patch.object(remediation_graph, 'decision_agent') as mock_decision, \
             patch.object(remediation_graph, 'validation_agent') as mock_validation, \
             patch.object(remediation_graph, 'workflow_agent') as mock_workflow, \
             patch.object(remediation_graph, 'sqs_tool') as mock_sqs, \
             patch.object(remediation_graph, 'notification_tool') as mock_notification, \
             patch.object(remediation_graph, 'remediation_validator') as mock_validator:
            
            # Setup all mock responses
            mock_decision.make_decision.return_value = RemediationDecision(
                decision_type="automatic",
                auto_approve=True,
                rationale="Low risk operation"
            )
            
            mock_validation.assess_feasibility.return_value = {
                "feasible": True,
                "overall_feasibility_score": 0.9,
                "automation_recommendation": "automatic"
            }
            
            mock_workflow.orchestrate_remediation.return_value = {
                "workflow_created": True,
                "workflow_id": "workflow-123",
                "steps": [{"action": "Update user preference"}],
                "status": "initiated"
            }
            
            mock_validator.validate_remediation_step.return_value = {
                "valid": True,
                "validation_score": 0.9,
                "errors": []
            }
            
            mock_sqs.send_remediation_signal.return_value = {
                "success": True,
                "message_id": "msg-123"
            }
            
            mock_notification.send_workflow_completed_notification.return_value = {
                "success": True,
                "notifications_sent": ["email"]
            }
            
            # Execute complete workflow
            final_result = await remediation_graph.process_remediation_signal(sample_remediation_signal)
            
            # Verify complete execution
            assert final_result["success"] is True
            assert final_result["workflow_completed"] is True
            assert len(final_result["notifications_sent"]) > 0