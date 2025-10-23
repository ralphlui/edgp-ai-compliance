"""
State management for remediation workflows using LangGraph
"""

from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime, timezone
import uuid
import logging

from .models import (
    RemediationSignal,
    RemediationWorkflow,
    RemediationDecision,
    WorkflowStatus,
    WorkflowType,
    RemediationType,
    HumanTask,
    RemediationMetrics
)

logger = logging.getLogger(__name__)


class RemediationStateSchema(TypedDict):
    """LangGraph state for remediation workflows"""

    # Input signal
    signal: RemediationSignal

    # Analysis results
    decision: Optional[RemediationDecision]
    feasibility_score: Optional[float]
    complexity_assessment: Optional[Dict[str, Any]]

    # Workflow management
    workflow: Optional[RemediationWorkflow]
    current_step: Optional[str]
    workflow_status: WorkflowStatus

    # Human intervention
    requires_human: bool
    human_task: Optional[HumanTask]
    approval_needed: bool

    # Tool outputs
    sqs_queue_created: bool
    sqs_queue_url: Optional[str]
    notification_sent: bool

    # Error handling
    errors: List[str]
    retry_count: int

    # Context and metadata
    context: Dict[str, Any]
    execution_path: List[str]


class RemediationState:
    """
    Lightweight remediation state container used by unit tests and
    simplified remediation workflows. Provides convenient list-based
    management of violations, decisions, and validations.
    """

    def __init__(self) -> None:
        self.violations: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []
        self.validations: List[Dict[str, Any]] = []
        self.workflow_status: str = "pending"
        self.metadata: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []

    def add_violation(self, violation: Dict[str, Any]) -> None:
        self.violations.append(violation)
        self.history.append({"event": "violation_added", "data": violation})

    def add_decision(self, decision: Dict[str, Any]) -> None:
        self.decisions.append(decision)
        self.history.append({"event": "decision_added", "data": decision})

    def add_validation(self, validation: Dict[str, Any]) -> None:
        self.validations.append(validation)
        self.history.append({"event": "validation_added", "data": validation})

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self.violations)

    def get_decisions(self) -> List[Dict[str, Any]]:
        return list(self.decisions)

    def get_validations(self) -> List[Dict[str, Any]]:
        return list(self.validations)

    def update_violation(self, violation_id: str, updated: Dict[str, Any]) -> None:
        for index, violation in enumerate(self.violations):
            if violation.get("violation_id") == violation_id or violation.get("id") == violation_id:
                self.violations[index] = updated
                self.history.append({"event": "violation_updated", "data": updated})
                break

    def remove_violation(self, violation_id: str) -> None:
        original = len(self.violations)
        self.violations = [
            violation for violation in self.violations
            if violation.get("violation_id") != violation_id and violation.get("id") != violation_id
        ]
        if len(self.violations) != original:
            self.history.append({"event": "violation_removed", "violation_id": violation_id})

    def count_violations_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for violation in self.violations:
            violation_type = violation.get("type", "unknown")
            counts[violation_type] = counts.get(violation_type, 0) + 1
        return counts

    def get_pending_decisions(self) -> List[Dict[str, Any]]:
        return [
            decision for decision in self.decisions
            if decision.get("status", "").lower() != "completed"
        ]

    def calculate_progress(self) -> float:
        if not self.decisions:
            return 0.0
        completed = sum(1 for decision in self.decisions if decision.get("status") == "completed")
        return completed / len(self.decisions)

    def filter_violations_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        return [
            violation for violation in self.violations
            if violation.get("severity") == severity
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations": list(self.violations),
            "decisions": list(self.decisions),
            "validations": list(self.validations),
            "workflow_status": self.workflow_status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationState":
        instance = cls()
        instance.violations = list(data.get("violations", []))
        instance.decisions = list(data.get("decisions", []))
        instance.validations = list(data.get("validations", []))
        instance.workflow_status = data.get("workflow_status", "pending")
        instance.metadata = dict(data.get("metadata", {}))
        return instance

    def clear(self) -> None:
        self.violations.clear()
        self.decisions.clear()
        self.validations.clear()
        self.history.append({"event": "state_cleared"})

    def validate(self) -> bool:
        # Basic validation: all violations should have an identifier
        for violation in self.violations:
            if not violation.get("violation_id") and not violation.get("id"):
                return False
        return True

    def create_snapshot(self) -> Dict[str, Any]:
        snapshot = self.to_dict()
        snapshot["history"] = list(self.history)
        return snapshot

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.violations = list(snapshot.get("violations", []))
        self.decisions = list(snapshot.get("decisions", []))
        self.validations = list(snapshot.get("validations", []))
        self.workflow_status = snapshot.get("workflow_status", "pending")
        self.metadata = dict(snapshot.get("metadata", {}))
        self.history = list(snapshot.get("history", []))
        self.history.append({"event": "state_restored"})

    def merge(self, other: "RemediationState") -> "RemediationState":
        merged = RemediationState()
        merged.violations = self.violations + other.violations
        merged.decisions = self.decisions + other.decisions
        merged.validations = self.validations + other.validations
        merged.workflow_status = other.workflow_status or self.workflow_status
        merged.metadata = {**self.metadata, **other.metadata}
        merged.history = self.history + other.history + [{"event": "states_merged"}]
        return merged


class RemediationStateManager:
    """
    Manages state for remediation workflows across the LangGraph execution
    """

    def __init__(self):
        self.active_workflows: Dict[str, RemediationWorkflow] = {}
        self.completed_workflows: Dict[str, RemediationWorkflow] = {}
        self.human_tasks: Dict[str, HumanTask] = {}
        self.metrics = RemediationMetrics()

    def create_initial_state(self, signal: RemediationSignal) -> RemediationStateSchema:
        """Create initial state for a new remediation request"""
        return RemediationStateSchema(
            signal=signal,
            decision=None,
            feasibility_score=None,
            complexity_assessment=None,
            workflow=None,
            current_step=None,
            workflow_status=WorkflowStatus.PENDING,
            requires_human=False,
            human_task=None,
            approval_needed=False,
            sqs_queue_created=False,
            sqs_queue_url=None,
            notification_sent=False,
            errors=[],
            retry_count=0,
            context={
                "started_at": datetime.now(timezone.utc),
                "violation_id": signal.violation.rule_id,
                "activity_id": signal.violation.activity_id,
                "signal_received_at": getattr(signal, "received_at", datetime.now(timezone.utc))
            },
            execution_path=[]
        )

    def update_decision(self, state: RemediationStateSchema, decision: RemediationDecision) -> RemediationStateSchema:
        """Update state with remediation decision"""
        state["decision"] = decision
        state["execution_path"].append("decision_made")

        # Update metrics
        self.metrics.total_violations_processed += 1
        if decision.remediation_type == RemediationType.AUTOMATIC:
            self.metrics.automatic_remediations += 1
        elif decision.remediation_type == RemediationType.HUMAN_IN_LOOP:
            self.metrics.human_loop_remediations += 1
        else:
            self.metrics.manual_remediations += 1

        return state

    def create_workflow(self, state: RemediationStateSchema) -> RemediationWorkflow:
        """Create a new remediation workflow"""
        workflow_id = f"remediation_{uuid.uuid4().hex[:8]}"

        workflow = RemediationWorkflow(
            id=workflow_id,
            violation_id=state["signal"].violation.rule_id,
            activity_id=state["signal"].violation.activity_id,
            remediation_type=state["decision"].remediation_type,
            workflow_type=self._map_remediation_to_workflow_type(state["decision"].remediation_type),
            priority=state["signal"].urgency,
            metadata={
                "framework": state["signal"].framework,
                "violation_description": state["signal"].violation.description,
                "remediation_actions": state["signal"].violation.remediation_actions
            }
        )

        self.active_workflows[workflow_id] = workflow
        state["workflow"] = workflow
        state["execution_path"].append("workflow_created")

        return workflow

    def add_workflow_step(
        self,
        workflow: RemediationWorkflow,
        step_name: str,
        step_description: str,
        action_type: str,
        parameters: Dict[str, Any] = None
    ) -> str:
        """Add a step to the workflow"""
        from .models import WorkflowStep

        step_id = f"step_{len(workflow.steps) + 1}_{uuid.uuid4().hex[:6]}"
        step = WorkflowStep(
            id=step_id,
            name=step_name,
            description=step_description,
            action_type=action_type,
            parameters=parameters or {}
        )

        workflow.steps.append(step)
        return step_id

    def update_workflow_status(
        self,
        state: RemediationStateSchema,
        status: WorkflowStatus,
        step_id: Optional[str] = None
    ) -> RemediationStateSchema:
        """Update workflow status"""
        if state["workflow"]:
            state["workflow"].status = status
            state["workflow_status"] = status

            if status == WorkflowStatus.IN_PROGRESS and not state["workflow"].started_at:
                state["workflow"].started_at = datetime.now(timezone.utc)
            elif status == WorkflowStatus.COMPLETED:
                state["workflow"].completed_at = datetime.now(timezone.utc)
                self._move_to_completed(state["workflow"])

            if step_id:
                for step in state["workflow"].steps:
                    if step.id == step_id:
                        step.status = status
                        break

        state["execution_path"].append(f"status_updated_{status}")
        return state

    def create_human_task(
        self,
        state: RemediationStateSchema,
        title: str,
        description: str,
        assignee: str,
        instructions: List[str] = None
    ) -> HumanTask:
        """Create a human task for manual intervention"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        task = HumanTask(
            id=task_id,
            workflow_id=state["workflow"].id if state["workflow"] else "unknown",
            title=title,
            description=description,
            assignee=assignee,
            priority=state["signal"].urgency,
            instructions=instructions or [],
            required_approvals=[]
        )

        self.human_tasks[task_id] = task
        state["human_task"] = task
        state["requires_human"] = True
        state["execution_path"].append("human_task_created")

        return task

    def add_error(self, state: RemediationStateSchema, error_message: str) -> RemediationStateSchema:
        """Add an error to the state"""
        state["errors"].append(f"{datetime.now(timezone.utc).isoformat()}: {error_message}")
        state["execution_path"].append("error_occurred")
        logger.error(f"Remediation error: {error_message}")
        return state

    def increment_retry(self, state: RemediationStateSchema) -> RemediationStateSchema:
        """Increment retry count"""
        state["retry_count"] += 1
        state["execution_path"].append(f"retry_{state['retry_count']}")
        return state

    def should_retry(self, state: RemediationStateSchema, max_retries: int = 3) -> bool:
        """Check if should retry based on retry count"""
        return state["retry_count"] < max_retries

    def update_sqs_info(self, state: RemediationStateSchema, queue_url: str) -> RemediationStateSchema:
        """Update SQS queue information"""
        state["sqs_queue_created"] = True
        state["sqs_queue_url"] = queue_url

        if state["workflow"]:
            state["workflow"].sqs_queue_url = queue_url

        state["execution_path"].append("sqs_queue_created")
        return state

    def mark_notification_sent(self, state: RemediationStateSchema) -> RemediationStateSchema:
        """Mark notification as sent"""
        state["notification_sent"] = True
        state["execution_path"].append("notification_sent")
        return state

    def get_workflow_summary(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a workflow"""
        workflow = self.active_workflows.get(workflow_id) or self.completed_workflows.get(workflow_id)

        if not workflow:
            return None

        return {
            "id": workflow.id,
            "status": workflow.status,
            "remediation_type": workflow.remediation_type,
            "priority": workflow.priority,
            "created_at": workflow.created_at,
            "completed_at": workflow.completed_at,
            "steps_total": len(workflow.steps),
            "steps_completed": len([s for s in workflow.steps if s.status == WorkflowStatus.COMPLETED]),
            "sqs_queue_url": workflow.sqs_queue_url
        }

    def get_metrics(self) -> RemediationMetrics:
        """Get current remediation metrics"""
        # Update success rate
        total = self.metrics.total_violations_processed
        if total > 0:
            completed = len([w for w in self.completed_workflows.values()
                           if w.status == WorkflowStatus.COMPLETED])
            self.metrics.success_rate = completed / total

        return self.metrics

    def _map_remediation_to_workflow_type(self, remediation_type: RemediationType) -> WorkflowType:
        """Map RemediationType to WorkflowType"""
        mapping = {
            RemediationType.AUTOMATIC: WorkflowType.AUTOMATIC,
            RemediationType.HUMAN_IN_LOOP: WorkflowType.HUMAN_IN_LOOP,
            RemediationType.MANUAL_ONLY: WorkflowType.MANUAL_ONLY
        }
        return mapping.get(remediation_type, WorkflowType.MANUAL_ONLY)

    def _move_to_completed(self, workflow: RemediationWorkflow):
        """Move workflow from active to completed"""
        if workflow.id in self.active_workflows:
            del self.active_workflows[workflow.id]
            self.completed_workflows[workflow.id] = workflow


# Alias retained for compatibility with components that expect a schema type.
LangGraphRemediationState = RemediationStateSchema
