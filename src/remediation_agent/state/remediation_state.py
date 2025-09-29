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


class RemediationState(TypedDict):
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


class RemediationStateManager:
    """
    Manages state for remediation workflows across the LangGraph execution
    """

    def __init__(self):
        self.active_workflows: Dict[str, RemediationWorkflow] = {}
        self.completed_workflows: Dict[str, RemediationWorkflow] = {}
        self.human_tasks: Dict[str, HumanTask] = {}
        self.metrics = RemediationMetrics()

    def create_initial_state(self, signal: RemediationSignal) -> RemediationState:
        """Create initial state for a new remediation request"""
        return RemediationState(
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
                "activity_id": signal.violation.activity_id
            },
            execution_path=[]
        )

    def update_decision(self, state: RemediationState, decision: RemediationDecision) -> RemediationState:
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

    def create_workflow(self, state: RemediationState) -> RemediationWorkflow:
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
        state: RemediationState,
        status: WorkflowStatus,
        step_id: Optional[str] = None
    ) -> RemediationState:
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
        state: RemediationState,
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

    def add_error(self, state: RemediationState, error_message: str) -> RemediationState:
        """Add an error to the state"""
        state["errors"].append(f"{datetime.now(timezone.utc).isoformat()}: {error_message}")
        state["execution_path"].append("error_occurred")
        logger.error(f"Remediation error: {error_message}")
        return state

    def increment_retry(self, state: RemediationState) -> RemediationState:
        """Increment retry count"""
        state["retry_count"] += 1
        state["execution_path"].append(f"retry_{state['retry_count']}")
        return state

    def should_retry(self, state: RemediationState, max_retries: int = 3) -> bool:
        """Check if should retry based on retry count"""
        return state["retry_count"] < max_retries

    def update_sqs_info(self, state: RemediationState, queue_url: str) -> RemediationState:
        """Update SQS queue information"""
        state["sqs_queue_created"] = True
        state["sqs_queue_url"] = queue_url

        if state["workflow"]:
            state["workflow"].sqs_queue_url = queue_url

        state["execution_path"].append("sqs_queue_created")
        return state

    def mark_notification_sent(self, state: RemediationState) -> RemediationState:
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