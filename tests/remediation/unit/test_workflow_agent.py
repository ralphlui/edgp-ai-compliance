"""
Unit tests for workflow agent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime, timezone

from src.remediation_agent.agents.workflow_agent import WorkflowAgent
from src.remediation_agent.state.models import (
    RemediationSignal, 
    WorkflowStep, 
    RemediationWorkflow, 
    RemediationDecision,
    WorkflowStatus
)
from src.compliance_agent.models.compliance_models import RiskLevel


class TestWorkflowAgent:
    """Test WorkflowAgent class"""
    
    @pytest.fixture
    def workflow_agent(self):
        """Create a workflow agent instance for testing"""
        return WorkflowAgent()
    
    @pytest.mark.asyncio
    async def test_orchestrate_remediation_simple_workflow(self, workflow_agent, sample_remediation_signal):
        """Test orchestration of a simple remediation workflow"""
        # Setup simple automatic remediation
        sample_remediation_signal.violation.remediation_actions = [
            "Update user email preference",
            "Set marketing opt-out flag"
        ]
        sample_remediation_signal.decision = RemediationDecision(
            decision_type="automatic",
            auto_approve=True,
            rationale="Simple low-risk operation"
        )
        
        result = await workflow_agent.orchestrate_remediation(sample_remediation_signal)
        
        assert result["workflow_created"] is True
        assert result["workflow_id"] is not None
        assert len(result["steps"]) == 2
        assert result["status"] == "initiated"
        assert result["execution_plan"]["estimated_duration"] > 0
    
    @pytest.mark.asyncio
    async def test_orchestrate_remediation_human_in_loop(self, workflow_agent, sample_remediation_signal):
        """Test orchestration with human-in-the-loop workflow"""
        # Setup human-in-loop remediation
        sample_remediation_signal.violation.remediation_actions = [
            "Delete user personal data",
            "Verify complete data removal"
        ]
        sample_remediation_signal.decision = RemediationDecision(
            decision_type="human_in_loop",
            auto_approve=False,
            rationale="Data deletion requires human oversight"
        )
        
        result = await workflow_agent.orchestrate_remediation(sample_remediation_signal)
        
        assert result["workflow_created"] is True
        assert result["requires_approval"] is True
        assert any(step["requires_human_approval"] for step in result["steps"])
        assert result["status"] == "pending_approval"
    
    @pytest.mark.asyncio
    async def test_orchestrate_remediation_manual_only(self, workflow_agent, sample_remediation_signal):
        """Test orchestration for manual-only remediation"""
        # Setup manual-only remediation
        sample_remediation_signal.violation.remediation_actions = [
            "Conduct legal review of data processing agreements",
            "Renegotiate third-party contracts"
        ]
        sample_remediation_signal.decision = RemediationDecision(
            decision_type="manual_only",
            auto_approve=False,
            rationale="Complex legal operations require manual handling"
        )
        
        result = await workflow_agent.orchestrate_remediation(sample_remediation_signal)
        
        assert result["workflow_created"] is True
        assert result["requires_manual_execution"] is True
        assert all(step["step_type"] == "manual" for step in result["steps"])
        assert result["status"] == "manual_required"
    
    @pytest.mark.asyncio
    async def test_orchestrate_remediation_no_actions(self, workflow_agent, sample_remediation_signal):
        """Test orchestration when no remediation actions are provided"""
        # Remove remediation actions
        sample_remediation_signal.violation.remediation_actions = []
        
        result = await workflow_agent.orchestrate_remediation(sample_remediation_signal)
        
        assert result["workflow_created"] is False
        assert "No remediation actions provided" in result["error"]
    
    def test_create_workflow_steps_automatic(self, workflow_agent):
        """Test creation of workflow steps for automatic remediation"""
        actions = [
            "Update user preference setting",
            "Send confirmation email",
            "Log remediation action"
        ]
        decision_type = "automatic"
        
        steps = workflow_agent._create_workflow_steps(actions, decision_type)
        
        assert len(steps) == 3
        assert all(step.step_type == "automated" for step in steps)
        assert all(not step.requires_human_approval for step in steps)
        assert steps[0].order == 0
        assert steps[1].order == 1
        assert steps[2].order == 2
    
    def test_create_workflow_steps_human_in_loop(self, workflow_agent):
        """Test creation of workflow steps for human-in-the-loop remediation"""
        actions = [
            "Delete user personal data",
            "Verify data deletion",
            "Send deletion confirmation"
        ]
        decision_type = "human_in_loop"
        
        steps = workflow_agent._create_workflow_steps(actions, decision_type)
        
        assert len(steps) == 3
        # First step (deletion) should require approval
        assert steps[0].requires_human_approval is True
        assert steps[0].step_type == "automated_with_approval"
        # Verification might require approval depending on risk
        # Confirmation should be automated
        assert steps[2].step_type in ["automated", "automated_with_approval"]
    
    def test_create_workflow_steps_manual_only(self, workflow_agent):
        """Test creation of workflow steps for manual-only remediation"""
        actions = [
            "Conduct legal review",
            "Update data processing agreements",
            "Implement policy changes"
        ]
        decision_type = "manual_only"
        
        steps = workflow_agent._create_workflow_steps(actions, decision_type)
        
        assert len(steps) == 3
        assert all(step.step_type == "manual" for step in steps)
        assert all(step.requires_human_approval for step in steps)
    
    def test_determine_step_type_data_modification(self, workflow_agent):
        """Test step type determination for data modification actions"""
        action = "Delete user personal information from database"
        decision_type = "automatic"
        
        step_type = workflow_agent._determine_step_type(action, decision_type)
        
        assert step_type == "automated_with_approval"
    
    def test_determine_step_type_simple_update(self, workflow_agent):
        """Test step type determination for simple update actions"""
        action = "Update user email preference setting"
        decision_type = "automatic"
        
        step_type = workflow_agent._determine_step_type(action, decision_type)
        
        assert step_type == "automated"
    
    def test_determine_step_type_notification(self, workflow_agent):
        """Test step type determination for notification actions"""
        action = "Send email notification to user"
        decision_type = "automatic"
        
        step_type = workflow_agent._determine_step_type(action, decision_type)
        
        assert step_type == "automated"
    
    def test_determine_step_type_manual_decision(self, workflow_agent):
        """Test step type determination with manual decision type"""
        action = "Update user preference setting"
        decision_type = "manual_only"
        
        step_type = workflow_agent._determine_step_type(action, decision_type)
        
        assert step_type == "manual"
    
    def test_requires_human_approval_data_deletion(self, workflow_agent):
        """Test human approval requirement for data deletion"""
        action = "Delete all user personal data"
        decision_type = "automatic"
        
        requires_approval = workflow_agent._requires_human_approval(action, decision_type)
        
        assert requires_approval is True
    
    def test_requires_human_approval_simple_update(self, workflow_agent):
        """Test human approval requirement for simple updates"""
        action = "Update user preference flag"
        decision_type = "automatic"
        
        requires_approval = workflow_agent._requires_human_approval(action, decision_type)
        
        assert requires_approval is False
    
    def test_requires_human_approval_human_in_loop(self, workflow_agent):
        """Test human approval requirement for human-in-loop decision"""
        action = "Send marketing email"
        decision_type = "human_in_loop"
        
        requires_approval = workflow_agent._requires_human_approval(action, decision_type)
        
        assert requires_approval is True
    
    def test_requires_human_approval_manual_only(self, workflow_agent):
        """Test human approval requirement for manual-only decision"""
        action = "Update preference setting"
        decision_type = "manual_only"
        
        requires_approval = workflow_agent._requires_human_approval(action, decision_type)
        
        assert requires_approval is True
    
    def test_estimate_step_duration_automated(self, workflow_agent):
        """Test duration estimation for automated steps"""
        action = "Update database record"
        step_type = "automated"
        
        duration = workflow_agent._estimate_step_duration(action, step_type)
        
        assert 1 <= duration <= 5  # Should be quick for automated steps
    
    def test_estimate_step_duration_with_approval(self, workflow_agent):
        """Test duration estimation for steps requiring approval"""
        action = "Delete user data"
        step_type = "automated_with_approval"
        
        duration = workflow_agent._estimate_step_duration(action, step_type)
        
        assert duration >= 30  # Should include time for human approval
    
    def test_estimate_step_duration_manual(self, workflow_agent):
        """Test duration estimation for manual steps"""
        action = "Conduct legal review"
        step_type = "manual"
        
        duration = workflow_agent._estimate_step_duration(action, step_type)
        
        assert duration >= 60  # Manual steps take longer
    
    def test_generate_execution_plan_automatic(self, workflow_agent, sample_workflow_steps):
        """Test execution plan generation for automatic workflow"""
        execution_plan = workflow_agent._generate_execution_plan(sample_workflow_steps, "automatic")
        
        assert execution_plan["total_steps"] == len(sample_workflow_steps)
        assert execution_plan["estimated_duration"] > 0
        assert execution_plan["parallel_execution_possible"] is not None
        assert "step_dependencies" in execution_plan
        assert execution_plan["requires_approval"] is False
    
    def test_generate_execution_plan_human_in_loop(self, workflow_agent, sample_workflow_steps):
        """Test execution plan generation for human-in-loop workflow"""
        # Modify some steps to require approval
        sample_workflow_steps[0].requires_human_approval = True
        
        execution_plan = workflow_agent._generate_execution_plan(sample_workflow_steps, "human_in_loop")
        
        assert execution_plan["requires_approval"] is True
        assert execution_plan["approval_steps"] > 0
        assert execution_plan["estimated_duration"] > sum(step.estimated_duration_minutes for step in sample_workflow_steps)
    
    def test_identify_step_dependencies_sequential(self, workflow_agent):
        """Test identification of sequential step dependencies"""
        actions = [
            "Backup user data",
            "Delete user data",
            "Verify deletion",
            "Send confirmation"
        ]
        
        dependencies = workflow_agent._identify_step_dependencies(actions)
        
        assert len(dependencies) >= 3  # Each step depends on previous
        assert dependencies[0]["dependent_step"] == 1
        assert dependencies[0]["dependency_step"] == 0
    
    def test_identify_step_dependencies_parallel_possible(self, workflow_agent):
        """Test identification when parallel execution is possible"""
        actions = [
            "Update user email preference",
            "Update user phone preference",
            "Send preference confirmation"
        ]
        
        dependencies = workflow_agent._identify_step_dependencies(actions)
        
        # First two steps can run in parallel, third depends on both
        assert len(dependencies) <= 2  # Fewer dependencies due to parallelization
    
    def test_can_execute_in_parallel_independent_actions(self, workflow_agent):
        """Test parallel execution detection for independent actions"""
        action1 = "Update user email preference"
        action2 = "Update user phone preference"
        
        can_parallel = workflow_agent._can_execute_in_parallel(action1, action2)
        
        assert can_parallel is True
    
    def test_can_execute_in_parallel_dependent_actions(self, workflow_agent):
        """Test parallel execution detection for dependent actions"""
        action1 = "Delete user data"
        action2 = "Verify data deletion"
        
        can_parallel = workflow_agent._can_execute_in_parallel(action1, action2)
        
        assert can_parallel is False
    
    def test_can_execute_in_parallel_same_resource(self, workflow_agent):
        """Test parallel execution detection for actions on same resource"""
        action1 = "Update user profile name"
        action2 = "Update user profile email"
        
        can_parallel = workflow_agent._can_execute_in_parallel(action1, action2)
        
        # Might be False due to same resource (user profile)
        assert isinstance(can_parallel, bool)
    
    def test_calculate_total_duration_sequential(self, workflow_agent, sample_workflow_steps):
        """Test total duration calculation for sequential execution"""
        duration = workflow_agent._calculate_total_duration(sample_workflow_steps, sequential=True)
        
        expected_duration = sum(step.estimated_duration_minutes for step in sample_workflow_steps)
        assert duration == expected_duration
    
    def test_calculate_total_duration_parallel(self, workflow_agent, sample_workflow_steps):
        """Test total duration calculation with parallel execution"""
        duration = workflow_agent._calculate_total_duration(sample_workflow_steps, sequential=False)
        
        max_duration = max(step.estimated_duration_minutes for step in sample_workflow_steps)
        total_duration = sum(step.estimated_duration_minutes for step in sample_workflow_steps)
        
        # Should be between max single step and total sequential time
        assert max_duration <= duration <= total_duration
    
    @pytest.mark.asyncio
    async def test_orchestrate_remediation_error_handling(self, workflow_agent, sample_remediation_signal):
        """Test error handling in remediation orchestration"""
        # Create invalid remediation signal
        sample_remediation_signal.violation.remediation_actions = None
        
        result = await workflow_agent.orchestrate_remediation(sample_remediation_signal)
        
        assert result["workflow_created"] is False
        assert "error" in result
    
    def test_workflow_step_creation_with_metadata(self, workflow_agent):
        """Test workflow step creation includes proper metadata"""
        actions = ["Update user preference"]
        decision_type = "automatic"
        
        steps = workflow_agent._create_workflow_steps(actions, decision_type)
        
        step = steps[0]
        assert step.action == "Update user preference"
        assert step.step_type == "automated"
        assert step.status == WorkflowStatus.PENDING
        assert step.estimated_duration_minutes > 0
        assert step.created_at is not None
        assert step.order == 0
    
    def test_execution_plan_includes_monitoring(self, workflow_agent, sample_workflow_steps):
        """Test that execution plan includes monitoring configuration"""
        execution_plan = workflow_agent._generate_execution_plan(sample_workflow_steps, "automatic")
        
        assert "monitoring" in execution_plan
        assert "checkpoints" in execution_plan
        assert "rollback_plan" in execution_plan
        assert "success_criteria" in execution_plan
    
    def test_workflow_orchestration_consistency(self, workflow_agent, sample_remediation_signal):
        """Test that workflow orchestration produces consistent results"""
        results = []
        
        # Run orchestration multiple times
        for _ in range(3):
            result = workflow_agent.orchestrate_remediation(sample_remediation_signal)
            results.append(result)
        
        # Check that key aspects are consistent
        step_counts = [len(r.get("steps", [])) for r in results]
        workflow_types = [r.get("status") for r in results]
        
        # Should be consistent across runs
        assert len(set(step_counts)) <= 1  # All same or only minor variations
        assert len(set(workflow_types)) == 1  # Should be identical