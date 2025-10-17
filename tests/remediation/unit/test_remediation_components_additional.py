"""
Additional tests targeting remediation components with large remaining coverage gaps.

These tests exercise execution nodes, human loop helpers, workflow state management,
graph utilities, and agent orchestration with controlled fakes to avoid external side
effects while covering diverse control-flow paths.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.remediation_agent.agents.workflow_agent import WorkflowAgent
from src.remediation_agent.graphs.nodes.execution_node import (
    ExecutionNode,
    ExecutionStatus,
    DataDeletionExecutor,
    DataUpdateExecutor,
    NotificationExecutor,
)
from src.remediation_agent.graphs.nodes.human_loop_node import HumanLoopNode
from src.remediation_agent.graphs.nodes.workflow_node import WorkflowNode
from src.remediation_agent.graphs.remediation_graph import RemediationGraph
from src.remediation_agent.state.remediation_state import RemediationStateManager
from src.remediation_agent.state.models import (
    RemediationDecision,
    RemediationType,
    RemediationWorkflow,
    RemediationMetrics,
    WorkflowType,
    WorkflowStep,
    WorkflowStatus,
    HumanTask,
    RiskLevel,
)
from src.remediation_agent.tools.sqs_tool import SQSTool
from src.remediation_agent.tools.notification_tool import NotificationTool, NotificationPriority
from src.remediation_agent.main import RemediationAgent
from src.remediation_agent.agents.validation_agent import ValidationAgent
from src.remediation_agent.state import remediation_state


@pytest.fixture
def fast_sleep(monkeypatch):
    """Replace asyncio.sleep to keep async pathways fast."""

    async def _sleep_stub(*args, **kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", _sleep_stub)


def _prepare_signal(signal, urgency: RiskLevel) -> None:
    """Attach commonly expected dynamic attributes onto fixture signals."""

    signal.__dict__["urgency"] = urgency
    signal.__dict__["received_at"] = datetime.now(timezone.utc)
    signal.context.setdefault("user_id", "user-789")
    signal.context.setdefault("field_name", "email")
    signal.context.setdefault("domain_name", "core_db")
    signal.context.setdefault("from_value", "old")
    signal.context.setdefault("to_value", "new")
    signal.context.setdefault("message", "Completed remediation")
    signal.context.setdefault("recipient", "team@example.com")
    signal.context.setdefault("create_backup", True)


@pytest.mark.asyncio
async def test_execution_node_handles_varied_actions(
    sample_remediation_signal,
    sample_remediation_decision,
    fast_sleep,
):
    """Cover delete/update/notify execution branches including unknown actions."""

    _prepare_signal(sample_remediation_signal, RiskLevel.MEDIUM)

    manager = RemediationStateManager()
    state = manager.create_initial_state(sample_remediation_signal)

    decision = sample_remediation_decision.model_copy(
        update={"remediation_type": RemediationType.HUMAN_IN_LOOP, "confidence_score": 0.8}
    )
    state["decision"] = decision

    steps = [
        WorkflowStep(
            id="step-delete",
            name="Delete Personal Data",
            action_type="delete_user_data",
        ),
        WorkflowStep(
            id="step-update",
            name="Update Preference",
            action_type="update_preference",
        ),
        WorkflowStep(
            id="step-notify",
            name="Notify Compliance Team",
            action_type="notify_compliance_team",
        ),
        WorkflowStep(
            id="step-unknown",
            name="Unsupported Step",
            action_type="custom_action",
        ),
    ]

    workflow = RemediationWorkflow(
        id="wf-exec-001",
        violation_id=sample_remediation_signal.violation.rule_id,
        activity_id=sample_remediation_signal.activity.id,
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        workflow_type=WorkflowType.HUMAN_IN_LOOP,
        steps=steps,
    )
    state["workflow"] = workflow

    node = ExecutionNode()
    state = await node(state)

    statuses = [result["status"] for result in state["execution_results"]]
    assert ExecutionStatus.COMPLETED.value in statuses
    assert ExecutionStatus.FAILED.value in statuses  # Unknown action path
    assert any("steps_executed" in result for result in state["execution_results"])
    assert state["context"]["execution_completed"] is True


@pytest.mark.asyncio
async def test_execution_node_extensibility(sample_remediation_signal, fast_sleep):
    """Validate custom executor registration and diagnostic helpers."""

    class EchoExecutor(DataDeletionExecutor):
        async def execute(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
            return {"status": ExecutionStatus.COMPLETED.value, "echo": parameters, "message": "ok"}

    _prepare_signal(sample_remediation_signal, RiskLevel.MEDIUM)
    manager = RemediationStateManager()
    state = manager.create_initial_state(sample_remediation_signal)

    node = ExecutionNode()
    node.add_executor("delete", EchoExecutor())
    probe = await node.test_execution("delete", {"user_id": "user-789"})
    assert probe["status"] == ExecutionStatus.COMPLETED.value

    failure = await node.test_execution("unknown", {})
    assert failure["status"] == ExecutionStatus.FAILED.value


@pytest.mark.asyncio
async def test_workflow_node_progress_and_summary(
    sample_remediation_signal,
    sample_remediation_decision,
    fast_sleep,
    monkeypatch,
):
    """Exercise workflow node helper routines outside the main path."""

    _prepare_signal(sample_remediation_signal, RiskLevel.HIGH)
    manager = RemediationStateManager()
    state = manager.create_initial_state(sample_remediation_signal)

    decision = sample_remediation_decision.model_copy(
        update={"remediation_type": RemediationType.HUMAN_IN_LOOP, "confidence_score": 0.7}
    )
    state["decision"] = decision

    workflow_node = WorkflowNode()

    fake_workflow = RemediationWorkflow(
        id="wf-node-001",
        violation_id=sample_remediation_signal.violation.rule_id,
        activity_id=sample_remediation_signal.activity.id,
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        workflow_type=WorkflowType.HUMAN_IN_LOOP,
        steps=[
            WorkflowStep(
                id="wf-step-1",
                name="Initial Review",
                action_type="human_review",
            ),
            WorkflowStep(
                id="wf-step-2",
                name="Finalize",
                action_type="api_call",
            ),
        ],
    )
    fake_workflow.sqs_queue_url = "https://mock-queue"

    workflow_node.workflow_agent = MagicMock()
    workflow_node.workflow_agent.create_workflow = AsyncMock(return_value=fake_workflow)
    workflow_node.workflow_agent.execute_workflow_step = AsyncMock(
        return_value={"success": True, "step_id": "wf-step-2"}
    )

    workflow_node.sqs_tool = MagicMock()
    workflow_node.sqs_tool.get_queue_attributes = AsyncMock(
        return_value={"success": True, "message_count": 2, "messages_in_flight": 1}
    )
    state["workflow"] = fake_workflow
    state["sqs_queue_url"] = "https://mock-queue"
    state["sqs_queue_created"] = True
    state["context"]["human_task_required"] = False

    await workflow_node._initialize_human_loop_workflow(state)

    workflow = state["workflow"]
    workflow.steps[0].status = WorkflowStatus.COMPLETED

    next_step_result = await workflow_node.execute_next_workflow_step(state)
    assert next_step_result["success"] is True

    progress = await workflow_node.monitor_workflow_progress(state)
    assert progress["workflow_id"] == workflow.id
    assert progress["queue_stats"]["messages_available"] == 2

    summary = workflow_node.get_workflow_summary(state)
    assert summary["workflow_id"] == workflow.id

    assert workflow_node.should_proceed_to_human_loop(state) is True


def test_remediation_state_manager_lifecycle(
    sample_remediation_signal,
    sample_remediation_decision,
    sample_workflow_step,
):
    """Cover state manager helpers including workflow summary retrieval."""

    _prepare_signal(sample_remediation_signal, RiskLevel.MEDIUM)
    manager = RemediationStateManager()
    state = manager.create_initial_state(sample_remediation_signal)
    decision = sample_remediation_decision.model_copy()
    state = manager.update_decision(state, decision)
    workflow = manager.create_workflow(state)
    step_id = manager.add_workflow_step(
        workflow,
        "Review Evidence",
        "Review supporting evidence",
        "human_review",
        {"prerequisites": ["evidence_uploaded"]},
    )
    assert step_id.startswith("step_")

    manager.update_workflow_status(state, WorkflowStatus.IN_PROGRESS)
    human_task = manager.create_human_task(
        state,
        "Approve remediation",
        "Final approval",
        "dpo@example.com",
        ["Verify logs", "Confirm deletion"],
    )
    assert human_task.id in manager.human_tasks

    manager.update_workflow_status(state, WorkflowStatus.COMPLETED)
    summary = manager.get_workflow_summary(workflow.id)
    assert summary is not None
    assert summary["status"] == WorkflowStatus.COMPLETED


def test_remediation_graph_utilities(sample_remediation_signal, sample_remediation_decision):
    """Use lightweight stubs to cover graph helper logic without running LangGraph."""

    graph = RemediationGraph.__new__(RemediationGraph)
    graph.state_manager = RemediationStateManager()
    graph.workflow_node = SimpleNamespace(get_workflow_summary=lambda state: {"workflow": "summary"})
    graph.human_loop_node = SimpleNamespace(
        get_human_loop_summary=lambda state: {"human": "summary"}
    )

    state = {"errors": [], "decision": sample_remediation_decision}
    sample_remediation_decision.remediation_type = RemediationType.AUTOMATIC

    assert graph._route_after_workflow_creation(state) == "automatic_execution"
    sample_remediation_decision.remediation_type = RemediationType.HUMAN_IN_LOOP
    assert graph._route_after_workflow_creation(state) == "human_intervention"

    state["errors"] = ["Critical failure detected"]
    assert graph._route_after_workflow_creation(state) == "error"

    execution_state = {
        "context": {"started_at": datetime.now(timezone.utc).isoformat()},
        "execution_path": ["step1", "step2"],
        "errors": ["oops"],
        "requires_human": True,
        "workflow": None,
    }
    metrics = graph._calculate_execution_metrics(execution_state)
    assert metrics["errors_encountered"] == 1

    sample_remediation_decision.remediation_type = RemediationType.HUMAN_IN_LOOP
    execution_state["decision"] = sample_remediation_decision
    execution_state["workflow"] = RemediationWorkflow(
        id="wf",
        violation_id="v",
        activity_id="a",
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        workflow_type=RemediationType.HUMAN_IN_LOOP,
    )
    next_steps = graph._determine_next_steps(execution_state)
    assert any("human" in step.lower() for step in next_steps)

    graph.compiled_graph = SimpleNamespace(
        get_graph=lambda: SimpleNamespace(draw_ascii=lambda: "ASCII GRAPH")
    )
    visualization = graph.get_graph_visualization()
    assert visualization["ascii_graph"] == "ASCII GRAPH"


@pytest.mark.asyncio
async def test_remediation_agent_process_with_mocks(
    sample_compliance_violation,
    sample_data_processing_activity,
    fast_sleep,
    monkeypatch,
):
    """Cover the high-level agent orchestration with stubbed graph + notifications."""

    async def fake_process(signal, config=None):
        return {"success": True, "workflow_id": "wf-123", "execution_path": ["analyze", "decide"]}

    async def fake_status(violation_id):
        return {"found": True, "violation_id": violation_id}

    async def fake_resume(violation_id, config=None):
        return {"success": True, "resumed": True, "violation_id": violation_id}

    monkeypatch.setattr(RemediationGraph, "__init__", lambda self: None)
    monkeypatch.setattr(
        RemediationGraph, "process_remediation_signal", AsyncMock(side_effect=fake_process)
    )
    monkeypatch.setattr(RemediationGraph, "get_workflow_status", AsyncMock(side_effect=fake_status))
    monkeypatch.setattr(RemediationGraph, "resume_workflow", AsyncMock(side_effect=fake_resume))

    from src.remediation_agent.state.models import RemediationSignal

    def create_signal(self, violation, activity, framework, urgency, context):
        signal = RemediationSignal(
            violation=violation,
            activity=activity,
            framework=framework,
            urgency=urgency or violation.risk_level,
            context=context or {},
            received_at=datetime.now(timezone.utc),
        )
        signal.__dict__["urgency"] = urgency or violation.risk_level
        return signal

    monkeypatch.setattr(RemediationAgent, "_create_remediation_signal", create_signal)

    agent = RemediationAgent.__new__(RemediationAgent)
    agent.graph = RemediationGraph()
    agent.graph.state_manager = RemediationStateManager()
    agent.graph.state_manager = RemediationStateManager()
    agent.graph.state_manager = RemediationStateManager()
    agent.notification_tool = MagicMock()
    agent.notification_tool.send_workflow_notification = AsyncMock(return_value={"success": True})
    agent.notification_tool.send_deadline_reminder = AsyncMock(return_value={"success": True})
    agent.metrics = RemediationMetrics()
    agent.config = {"enable_notifications": True}
    agent._send_completion_notification = AsyncMock(return_value=None)

    result = await RemediationAgent.process_compliance_violation(
        agent, sample_compliance_violation, sample_data_processing_activity, framework="gdpr_eu"
    )
    assert result["success"] is True

    status = await RemediationAgent.get_workflow_status(agent, sample_compliance_violation.rule_id)
    assert status["found"] is True

    resume = await RemediationAgent.resume_workflow(agent, sample_compliance_violation.rule_id)
    assert resume["resumed"] is True


def test_sqs_tool_signal_utilities(sample_remediation_signal, sample_remediation_decision):
    """Cover serialization and attribute helpers along with mock fallbacks."""

    tool = SQSTool()
    tool.sqs_client = None  # Force mock mode
    tool.queue_urls["default"] = "https://mock-queue"

    payload = tool.serialize_remediation_signal(sample_remediation_signal)
    assert "signal_id" in payload

    decision_copy = sample_remediation_decision.model_copy()
    decision_copy.__dict__["priority"] = 1
    signal_with_decision = sample_remediation_signal.model_copy(update={"decision": decision_copy})
    attrs = tool.create_message_attributes(signal_with_decision)
    assert "signal_id" in attrs

    mock_queue = tool._create_mock_queue("test", "wf")
    assert mock_queue["mock"] is True
    mock_message = tool._send_mock_message("https://mock", {"foo": "bar"})
    assert mock_message["mock"] is True
    mock_attrs = tool._get_mock_queue_attributes("https://mock")
    assert mock_attrs["mock"] is True


@pytest.mark.asyncio
async def test_validation_agent_feasibility_analysis(
    sample_remediation_signal,
    sample_remediation_decision,
    fast_sleep,
):
    """Hit validation agent feasibility scoring logic with realistic signal inputs."""

    agent = ValidationAgent()
    _prepare_signal(sample_remediation_signal, RiskLevel.HIGH)

    # Adjust decision to trigger warnings/errors.
    decision = sample_remediation_decision.model_copy(
        update={
            "confidence_score": 0.4,
            "estimated_effort": 600,
            "remediation_type": RemediationType.AUTOMATIC,
        }
    )

    feasibility, details = await agent.validate_remediation_feasibility(
        sample_remediation_signal, decision
    )
    assert 0.0 <= feasibility <= 1.0
    assert "blockers" in details

    validation_result = await agent.validate_decision(decision)
    assert validation_result.confidence_score <= 0.7

    action_analysis = agent._analyze_remediation_actions(["Delete account", "Notify DPO"])
    system_capabilities = agent._check_system_capabilities(sample_remediation_signal)
    integration_complexity = agent._analyze_integration_complexity(sample_remediation_signal)
    blockers = agent._identify_blockers(action_analysis, system_capabilities)
    prerequisites = agent._compile_prerequisites(action_analysis)
    risks = agent._identify_risk_factors(action_analysis, sample_remediation_signal)
    adjustments = agent._recommend_adjustments(0.2, RemediationType.AUTOMATIC)

    assert isinstance(blockers, list)
    assert isinstance(prerequisites, list)
    assert isinstance(risks, list)
    assert isinstance(adjustments, list)


@pytest.mark.asyncio
async def test_remediation_graph_process_signal_with_stub(sample_remediation_signal, fast_sleep):
    """Simulate LangGraph execution with a deterministic stub stream."""

    _prepare_signal(sample_remediation_signal, RiskLevel.MEDIUM)
    graph = RemediationGraph.__new__(RemediationGraph)
    graph.state_manager = RemediationStateManager()

    decision = RemediationDecision(
        violation_id=sample_remediation_signal.violation.rule_id,
        remediation_type=RemediationType.AUTOMATIC,
        confidence_score=0.9,
        reasoning="automated path",
        estimated_effort=30,
        risk_if_delayed=RiskLevel.MEDIUM,
    )

    workflow = RemediationWorkflow(
        id="wf-graph-001",
        violation_id=sample_remediation_signal.violation.rule_id,
        activity_id=sample_remediation_signal.activity.id,
        remediation_type=RemediationType.AUTOMATIC,
        workflow_type=WorkflowType.AUTOMATIC,
        steps=[],
    )

    final_state = {
        "signal": sample_remediation_signal,
        "execution_path": ["analysis_completed", "decision_completed", "workflow_completed"],
        "errors": [],
        "decision": decision,
        "workflow": workflow,
        "context": {"execution_metrics": {"nodes_executed": 3}},
        "requires_human": False,
    }

    initial_state = graph.state_manager.create_initial_state(sample_remediation_signal)

    class FakeCompiled:
        def __init__(self, steps):
            self._steps = steps

        async def astream(self, *_args, **_kwargs):
            for step in self._steps:
                yield step

        def get_graph(self):
            return SimpleNamespace(draw_ascii=lambda: "ASCII")

    graph.workflow_node = SimpleNamespace(get_workflow_summary=lambda state: {"workflow_id": workflow.id})
    graph.human_loop_node = SimpleNamespace(
        get_human_loop_summary=lambda state: {"requires_human": state.get("requires_human", False)},
        is_human_intervention_complete=lambda state: True,
    )

    graph.compiled_graph = FakeCompiled([
        {"analyze": initial_state},
        {"decide": {**initial_state, "decision": decision, "execution_path": ["analysis_completed"], "context": {}, "errors": []}},
        {"finalize": final_state},
    ])

    result = await graph.process_remediation_signal(sample_remediation_signal)
    assert result["success"] is True
    assert result["violation_id"] == sample_remediation_signal.violation.rule_id


@pytest.mark.asyncio
async def test_remediation_agent_batch_and_stop_workflows(
    sample_compliance_violation,
    sample_data_processing_activity,
    fast_sleep,
    monkeypatch,
):
    """Cover batch processing and emergency stop pathways in the agent."""

    monkeypatch.setattr(RemediationGraph, "__init__", lambda self: None)
    monkeypatch.setattr(RemediationGraph, "process_remediation_signal", AsyncMock(return_value={"success": True, "workflow_id": "wf-1"}))

    agent = RemediationAgent.__new__(RemediationAgent)
    agent.graph = RemediationGraph()
    agent.graph.state_manager = RemediationStateManager()
    agent.metrics = RemediationMetrics()
    agent.notification_tool = MagicMock()
    agent.notification_tool.send_workflow_notification = AsyncMock(return_value={"success": True})
    agent.notification_tool.send_urgent_alert = AsyncMock(return_value={"success": True})
    agent.config = {"enable_notifications": True, "max_concurrent_workflows": 2}
    agent._send_completion_notification = AsyncMock(return_value=None)

    async def fake_process(**kwargs):
        return {"success": True, "violation_id": kwargs["violation"].rule_id, "decision_info": {"remediation_type": "automatic"}, "signal_info": {"framework": "gdpr_eu"}}

    agent.process_compliance_violation = AsyncMock(side_effect=fake_process)

    violations = [
        {
            "violation": sample_compliance_violation,
            "activity": sample_data_processing_activity,
            "framework": "gdpr_eu",
        },
        {
            "violation": sample_compliance_violation,
            "activity": sample_data_processing_activity,
            "framework": "gdpr_eu",
        },
    ]

    batch_result = await RemediationAgent.process_multiple_violations(agent, violations)
    assert len(batch_result["results"]) == 2

    workflow = RemediationWorkflow(
        id=sample_compliance_violation.rule_id,
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        remediation_type=RemediationType.AUTOMATIC,
        workflow_type=WorkflowType.AUTOMATIC,
        metadata={},
    )
    agent.graph.state_manager.active_workflows[workflow.violation_id] = workflow

    stop_result = await agent.emergency_stop_workflow(workflow.violation_id, reason="test")
    assert stop_result["success"] is True
    assert agent.graph.state_manager.completed_workflows[workflow.id].status == WorkflowStatus.CANCELLED


@pytest.mark.asyncio
async def test_notification_tool_channel_senders(fast_sleep):
    tool = NotificationTool()
    content = {"subject": "Test", "body": "Body"}
    recipients = ["user@example.com"]

    email = await tool._send_email(content, recipients, NotificationPriority.HIGH)
    slack = await tool._send_slack(content, recipients, NotificationPriority.NORMAL)
    sms = await tool._send_sms(content, recipients, NotificationPriority.URGENT)
    webhook = await tool._send_webhook(content, recipients, NotificationPriority.NORMAL)
    in_app = await tool._send_in_app(content, recipients, NotificationPriority.LOW)

    assert email["success"] and slack["success"] and sms["success"]
    assert webhook["success"] and in_app["success"]


@pytest.mark.asyncio
async def test_sqs_tool_client_integration(monkeypatch):
    class StubClient:
        def __init__(self):
            self.queues: Dict[str, Dict[str, Any]] = {}

        def create_queue(self, QueueName, Attributes=None, tags=None):
            url = f"https://stub/{QueueName}"
            self.queues[QueueName] = {"Attributes": Attributes or {}, "Tags": tags or {}, "Url": url}
            return {"QueueUrl": url}

        def get_queue_attributes(self, QueueUrl, AttributeNames=None):
            name = QueueUrl.split("/")[-1]
            arn = f"arn:aws:sqs:stub:123:{name}"
            return {"Attributes": {"QueueArn": arn, "ApproximateNumberOfMessages": "1", "ApproximateNumberOfMessagesNotVisible": "0", "CreatedTimestamp": "0", "LastModifiedTimestamp": "0"}}

        def set_queue_attributes(self, QueueUrl, Attributes):
            name = QueueUrl.split("/")[-1]
            self.queues.setdefault(name, {})["RedrivePolicy"] = Attributes

        def receive_message(self, QueueUrl, MaxNumberOfMessages, WaitTimeSeconds, MessageAttributeNames):
            message = {"MessageId": "msg-1", "ReceiptHandle": "handle-1", "Body": '{"hello": "world"}', "MD5OfBody": "abc"}
            return {"Messages": [message]}

        def delete_message(self, QueueUrl, ReceiptHandle):
            return None

    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: StubClient())

    tool = SQSTool()
    tool.sqs_client = StubClient()

    dlq = await tool._create_dead_letter_queue("main", "wf")
    arn = await tool._get_queue_arn(dlq["queue_url"])
    await tool._configure_dead_letter_queue("https://stub/main", arn)

    messages = await tool.receive_workflow_messages("https://stub/main")
    assert messages["success"] is True

    await tool.delete_message("https://stub/main", "handle-1")
    attrs = await tool.get_queue_attributes("https://stub/main")
    assert attrs["success"] is True
