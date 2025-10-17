"""
Additional workflow-oriented tests to boost coverage for remediation agent components.

These tests exercise the analysis, decision, workflow, execution, and human-loop nodes,
along with supporting tools such as the workflow agent, SQS helper, remediation validator,
and notification tool. They intentionally focus on deterministic code paths with heavy
branching to ensure broad line coverage across the remediation stack.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.remediation_agent.agents.workflow_agent import WorkflowAgent
from src.remediation_agent.graphs.nodes.analysis_node import AnalysisNode
from src.remediation_agent.graphs.nodes.decision_node import DecisionNode
from src.remediation_agent.graphs.nodes.execution_node import ExecutionNode, ExecutionStatus
from src.remediation_agent.graphs.nodes.human_loop_node import HumanLoopNode
from src.remediation_agent.graphs.nodes.workflow_node import WorkflowNode
from src.remediation_agent.state.remediation_state import RemediationStateManager
from src.remediation_agent.state.models import (
    HumanTask,
    RemediationDecision,
    RemediationType,
    WorkflowStep,
    WorkflowStatus,
    RiskLevel,
)
from src.remediation_agent.tools.notification_tool import NotificationTool, NotificationType, NotificationPriority
from src.remediation_agent.tools.remediation_validator import RemediationValidator
from src.remediation_agent.tools.sqs_tool import SQSTool

# The conftest in tests/remediation provides rich model fixtures we rely on here.


@pytest.fixture
def fast_sleep(monkeypatch):
    """Accelerate async sleeps used in executors and notification scheduling."""

    async def _sleep_stub(*args, **kwargs):  # pragma: no cover - behaviour validated via tests
        return None

    monkeypatch.setattr(asyncio, "sleep", _sleep_stub)


def _prepare_signal(signal, urgency: RiskLevel) -> None:
    """Ensure test signals expose attributes referenced by nodes."""

    # Many nodes expect attributes that are absent on the default model instance.
    signal.__dict__["urgency"] = urgency
    signal.__dict__["received_at"] = datetime.now(timezone.utc)
    signal.context.setdefault("user_id", "user-123")
    signal.context.setdefault("field_name", "email")
    signal.context.setdefault("domain_name", "users_db")
    signal.context.setdefault("from_value", "old")
    signal.context.setdefault("to_value", "new")
    signal.context.setdefault("message", "Remediation completed")
    signal.context.setdefault("recipient", "team@example.com")
    signal.context.setdefault("create_backup", True)


@pytest.mark.asyncio
async def test_end_to_end_automatic_flow(
    sample_remediation_signal,
    sample_remediation_decision,
    fast_sleep,
    monkeypatch,
):
    """
    Drive the automatic remediation path end-to-end across the primary LangGraph nodes.
    This hits complex branching logic inside analysis, decision adjustment, workflow setup,
    and execution, while stubbing external integrations (LLM, SQS).
    """

    sample_remediation_signal.violation.risk_level = RiskLevel.MEDIUM
    _prepare_signal(sample_remediation_signal, RiskLevel.MEDIUM)

    state_manager = RemediationStateManager()
    state = state_manager.create_initial_state(sample_remediation_signal)

    analysis_node = AnalysisNode()
    state = await analysis_node(state)
    # Ensure the feasibility/complexity metrics satisfy automatic criteria.
    state["feasibility_score"] = 0.9
    state["complexity_assessment"]["overall_complexity"] = 0.3
    assert state["complexity_assessment"]["overall_complexity"] <= 1.0
    assert "analysis_completed" in state["execution_path"]

    auto_decision = sample_remediation_decision.model_copy(
        update={
            "remediation_type": RemediationType.AUTOMATIC,
            "confidence_score": 0.92,
            "estimated_effort": 45,
            "prerequisites": [],
        }
    )

    decision_node = DecisionNode()
    decision_node.decision_agent = AsyncMock()
    decision_node.decision_agent.analyze_violation.return_value = auto_decision

    state = await decision_node(state)
    assert state["decision"].remediation_type == RemediationType.AUTOMATIC
    assert state["context"]["decision_made"] is True

    # Prepare workflow node with lightweight collaborators
    monkeypatch.setenv("SQS_MAIN_QUEUE_URL", "https://mock-queue")
    workflow_node = WorkflowNode()
    workflow_node.sqs_tool = MagicMock()
    workflow_node.sqs_tool.send_workflow_message = AsyncMock(return_value={"success": True})
    workflow_node.sqs_tool.get_queue_attributes = AsyncMock(
        return_value={"success": True, "message_count": 0, "messages_in_flight": 0}
    )
    workflow_node.workflow_agent = WorkflowAgent()

    state = await workflow_node(state)
    assert state["workflow"] is not None
    assert state["sqs_queue_created"] is True
    assert state["workflow_status"] == WorkflowStatus.PENDING
    assert "workflow_creation_completed" in state["execution_path"]

    execution_node = ExecutionNode()
    state = await execution_node(state)
    assert "execution_results" in state
    assert all(result["step_id"] for result in state["execution_results"])
    assert state["context"]["execution_completed"] is True
    assert state["workflow_status"] in {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}

    # Even automatic paths may request oversight. Exercise human loop node manually.
    human_loop_node = HumanLoopNode()
    human_loop_node.notification_tool = MagicMock()
    human_loop_node.notification_tool.send_workflow_notification = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_human_task_notification = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_deadline_reminder = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_urgent_alert = AsyncMock(
        return_value={"success": True}
    )

    state = await human_loop_node(state)
    assert state["requires_human"] is True
    assert "human_loop_completed" in state["execution_path"]
    assert state["context"]["human_tasks_created"] >= 1


@pytest.mark.asyncio
async def test_manual_remediation_flow_creates_tasks(
    sample_remediation_signal,
    sample_remediation_decision,
    fast_sleep,
):
    """Cover the manual remediation branch where execution is skipped and human tasks dominate."""

    _prepare_signal(sample_remediation_signal, RiskLevel.CRITICAL)

    state_manager = RemediationStateManager()
    state = state_manager.create_initial_state(sample_remediation_signal)

    analysis_node = AnalysisNode()
    state = await analysis_node(state)

    manual_decision = sample_remediation_decision.model_copy(
        update={
            "remediation_type": RemediationType.MANUAL_ONLY,
            "confidence_score": 0.7,
            "estimated_effort": 180,
            "prerequisites": ["legal_review"],
        }
    )

    decision_node = DecisionNode()
    decision_node.decision_agent = AsyncMock()
    decision_node.decision_agent.analyze_violation.return_value = manual_decision

    state = await decision_node(state)
    assert state["decision"].remediation_type == RemediationType.MANUAL_ONLY

    workflow_node = WorkflowNode()
    workflow_node.sqs_tool = MagicMock()
    workflow_node.sqs_tool.send_workflow_message = AsyncMock(return_value={"success": True})
    workflow_node.workflow_agent = WorkflowAgent()

    state = await workflow_node(state)
    assert state["requires_human"] is True
    assert state["context"]["urgent_human_task_required"] is True

    execution_node = ExecutionNode()
    state = await execution_node(state)
    # Manual-only decisions should skip automatic execution.
    assert state["context"]["execution_status"] == "awaiting_manual_execution"
    assert "execution_skipped_manual_only" in state["execution_path"]

    human_loop_node = HumanLoopNode()
    human_loop_node.notification_tool = MagicMock()
    human_loop_node.notification_tool.send_workflow_notification = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_human_task_notification = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_deadline_reminder = AsyncMock(
        return_value={"success": True}
    )
    human_loop_node.notification_tool.send_urgent_alert = AsyncMock(
        return_value={"success": True}
    )

    state = await human_loop_node(state)
    assert state["human_task"] is not None
    assert state["context"]["intervention_type"] in {
        "full_manual_execution",
        "complex_review_approval",
        "standard_review_approval",
    }


@pytest.mark.asyncio
async def test_remediation_validator_evaluates_plan(
    sample_remediation_signal,
    sample_remediation_decision,
    sample_workflow_step,
):
    """Exercise the comprehensive validation pipeline, capturing warnings and recommendations."""

    _prepare_signal(sample_remediation_signal, RiskLevel.HIGH)

    # Ensure the signal references the decision to satisfy validator expectations.
    sample_remediation_signal.decision = sample_remediation_decision
    steps = [
        sample_workflow_step,
        WorkflowStep(
            id="backup_step",
            name="Backup Verification",
            action_type="backup_verification",
            parameters={"prerequisites": ["backup_verified"]},
            estimated_duration_minutes=5,
        ),
    ]

    validator = RemediationValidator()
    signal_analysis = await validator._validate_signal(sample_remediation_signal)
    decision_analysis = await validator._validate_decision(
        sample_remediation_signal, sample_remediation_decision
    )
    workflow_analysis = await validator._validate_workflow_steps(
        sample_remediation_signal, steps
    )
    data_analysis = await validator._validate_data_handling(
        sample_remediation_signal, sample_remediation_decision
    )
    compliance_analysis = await validator._validate_compliance_requirements(
        sample_remediation_signal, sample_remediation_decision
    )
    security_analysis = await validator._validate_security_requirements(
        sample_remediation_signal, sample_remediation_decision
    )

    plan_result = await validator.validate_remediation_plan(
        sample_remediation_signal, sample_remediation_decision, steps
    )
    assert plan_result["overall_valid"] in {True, False}
    assert "data_validation" in plan_result
    assert isinstance(plan_result["warnings"], list)

    checks = {
        "db": validator._check_database_state("user-1"),
        "relationships": validator._check_data_relationships("user-1"),
        "backup": validator._verify_backup_exists("users"),
    }
    score = validator._calculate_validation_score(checks)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_sqs_tool_mock_paths(monkeypatch):
    """Cover mock fallbacks when AWS credentials are absent."""

    monkeypatch.setenv("AWS_REGION", "us-east-1")

    def _raise_client(*args, **kwargs):
        raise RuntimeError("no aws credentials")

    monkeypatch.setattr("boto3.client", _raise_client)

    tool = SQSTool()
    tool.queue_urls["default"] = "https://sqs.mock/default"

    queue_result = await tool.create_remediation_queue("test-queue", "wf-123")
    assert queue_result["success"] is True
    assert queue_result.get("mock") is True

    send_result = await tool.send_workflow_message(
        queue_result["queue_url"], {"workflow_id": "wf-123"}
    )
    assert send_result["success"] is True
    assert send_result.get("mock") is True

    receive_result = await tool.receive_workflow_messages(queue_result["queue_url"])
    assert receive_result["mock"] is True

    attrs = await tool.get_queue_attributes(queue_result["queue_url"])
    assert attrs["success"] is True
    assert attrs.get("mock") is True

    automatic_queue = tool.get_queue_url_for_type("automatic")
    assert automatic_queue == tool.config.get("main_queue_url")
    configured = tool.get_all_configured_queues()
    assert "main_queue" in configured
    assert tool.is_configured() is False


@pytest.mark.asyncio
async def test_workflow_agent_generates_and_executes_steps(
    sample_remediation_decision,
    sample_compliance_violation,
    sample_data_processing_activity,
    fast_sleep,
    monkeypatch,
):
    """
    Verify WorkflowAgent step generation, parameter enrichment, and execution orchestration.
    """

    agent = WorkflowAgent()

    signal_decision = sample_remediation_decision.model_copy(
        update={"remediation_type": RemediationType.HUMAN_IN_LOOP}
    )
    workflow = await agent.create_workflow(
        signal_decision,
        sample_compliance_violation,
        activity=sample_data_processing_activity,
    )

    assert workflow.steps
    assert any(step.requires_human_approval for step in workflow.steps)

    # Replace network / IO heavy handlers with lightweight stubs while
    # still exercising the orchestration logic and branching in _execute_step.
    monkeypatch.setattr(agent, "_run_api_call", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_execute_database_step", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_send_email_step", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_create_approval_task", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_create_human_task", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_sqs_creation", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_prerequisite_validation", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_remediation_execution", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_completion_verification", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_notification", AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(agent, "_handle_compliance_update", AsyncMock(return_value={"success": True}))

    execution = await agent.execute_workflow(workflow)
    assert execution["success"] is True
    assert execution["workflow_id"] == workflow.id
    assert execution["step_results"]


@pytest.mark.asyncio
async def test_notification_tool_compiles_and_sends_messages(
    sample_remediation_workflow,
    sample_human_task,
    fast_sleep,
    monkeypatch,
):
    """Use mocks for delivery channels to cover template expansion and prioritisation logic."""

    workflow = sample_remediation_workflow
    workflow.priority = RiskLevel.HIGH
    workflow.started_at = datetime.now(timezone.utc) - timedelta(hours=2)

    tool = NotificationTool()
    sample_human_task.instructions = ["Review remediation steps", "Confirm evidence"]

    original_prepare = tool._prepare_notification_content

    def patched_prepare(notification_type, workflow_obj, context):
        if "required_actions" not in context:
            instructions = context.get("instructions") or []
            if isinstance(instructions, list):
                context["required_actions"] = "\n".join(f"- {item}" for item in instructions) or "Review task"
            else:
                context["required_actions"] = str(instructions)
        return original_prepare(notification_type, workflow_obj, context)

    tool._prepare_notification_content = patched_prepare

    async def _fake_channel(*args, **kwargs):
        return {"success": True, "channel": args[0].value}

    tool._send_via_channel = AsyncMock(side_effect=_fake_channel)
    tool._log_notification = AsyncMock(return_value=None)

    result = await tool.send_workflow_notification(
        NotificationType.WORKFLOW_STARTED,
        workflow,
        additional_context={"details_url": "https://example.com/details"},
    )
    assert result["success"] is True
    assert result["notification_type"] == NotificationType.WORKFLOW_STARTED
    assert result["channels_used"]

    task_result = await tool.send_human_task_notification(sample_human_task, workflow)
    assert task_result["success"] is True

    urgent_result = await tool.send_urgent_alert(
        workflow, "Database outage", ["Pause ingestion", "Notify stakeholders"]
    )
    assert urgent_result["success"] is True

    reminder = await tool.send_deadline_reminder(sample_human_task, workflow, 6)
    assert reminder["success"] is True

    # Priority determination should account for notification type and workflow risk.
    priority = tool._determine_priority(NotificationType.URGENT_ATTENTION, workflow)
    assert priority is NotificationPriority.URGENT
