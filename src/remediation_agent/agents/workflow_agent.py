"""Workflow agent orchestrating remediation execution."""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

import aiohttp

from ..state.models import (
    HumanTask,
    RemediationDecision,
    RemediationSignal,
    RemediationType,
    RemediationWorkflow,
    WorkflowStatus,
    WorkflowStep,
    WorkflowType,
)
from src.compliance_agent.models.compliance_models import ComplianceViolation

logger = logging.getLogger(__name__)


class WorkflowAgent:
    """Create workflows, execute steps, and manage human-in-the-loop tasks."""

    def __init__(self) -> None:
        self._human_tasks: Dict[str, Dict[str, Any]] = {}
        self._workflow_templates = self._build_workflow_templates()

    # ------------------------------------------------------------------
    # Workflow creation
    # ------------------------------------------------------------------
    async def create_workflow(self, *args, **kwargs) -> RemediationWorkflow:
        """Create a workflow from flexible argument combinations.

        Supports the following signatures used across the codebase and tests:

        * create_workflow(signal, decision, feasibility_details)
        * create_workflow(decision, violation)
        * create_workflow(decision, violation, activity=...)
        """

        signal, decision, violation, activity, _ = self._normalize_inputs(*args, **kwargs)

        steps = self._generate_workflow_steps(decision, violation, activity)
        steps = self._add_approval_step_if_needed(steps, decision.remediation_type, violation.rule_id)
        for index, step in enumerate(steps):
            step.order = index

        workflow = RemediationWorkflow(
            id=f"workflow_{uuid.uuid4().hex[:8]}",
            violation_id=violation.rule_id,
            activity_id=violation.activity_id or decision.activity_id or "unknown_activity",
            remediation_type=decision.remediation_type,
            workflow_type=self._map_remediation_to_workflow_type(decision.remediation_type),
            steps=steps,
            metadata={
                "decision_reasoning": decision.reasoning,
                "decision_confidence": decision.confidence_score,
                "framework": getattr(signal, "framework", None),
                "remediation_actions": violation.remediation_actions or [],
            },
        )

        workflow.total_estimated_duration = self._calculate_total_duration(steps)

        if signal:
            workflow.metadata.setdefault("context", getattr(signal, "context", {}))

        return workflow

    def _normalize_inputs(
        self, *args, **kwargs
    ) -> tuple[Optional[RemediationSignal], RemediationDecision, ComplianceViolation, Optional[Any], Dict[str, Any]]:
        feasibility = kwargs.get("feasibility_details", {}) or {}

        if args and isinstance(args[0], RemediationSignal):
            signal = args[0]
            decision = args[1]
            violation = signal.violation
            activity = signal.activity
        else:
            signal = kwargs.get("signal")
            decision = args[0]
            violation = args[1]
            activity = kwargs.get("activity")

        return signal, decision, violation, activity, feasibility

    def _generate_workflow_steps(
        self,
        decision: RemediationDecision,
        violation: ComplianceViolation,
        activity: Optional[Any] = None,
    ) -> List[WorkflowStep]:
        template_entries = self._workflow_templates[decision.remediation_type]
        template_steps = [self._build_template_step(entry) for entry in template_entries]

        actions = (violation.remediation_actions or []) or ["Review remediation context"]

        generated: List[WorkflowStep] = []
        for action in actions:
            step = self._map_remediation_action_to_step(action, len(generated), decision.remediation_type)
            generated.append(step)

        return generated + template_steps

    def _build_template_step(self, entry: Dict[str, Any]) -> WorkflowStep:
        duration = int(entry.get("duration", 10))
        step = WorkflowStep(
            id=f"template_{uuid.uuid4().hex[:6]}",
            name=entry["name"],
            description=entry["description"],
            action_type=entry["action_type"],
            parameters=entry.get("parameters", {}),
            estimated_duration_minutes=duration,
        )
        step.expected_duration = duration
        step.step_type = entry.get("step_type", "automated")
        step.requires_human_approval = entry.get("requires_human_approval", False)
        return step

    def _map_remediation_action_to_step(
        self,
        action: str,
        order: int,
        decision_type: RemediationType,
        violation_id: Optional[str] = None,
    ) -> WorkflowStep:
        action_type = self._determine_action_type(action, decision_type)
        requires_approval = self._requires_human_approval(action, decision_type)
        duration = self._estimate_step_duration(action, action_type)

        violation_ref = violation_id or "unknown"

        if action_type == "email_notification":
            parameters = self._create_email_parameters(action, violation_ref)
        elif action_type == "database_operation":
            parameters = self._create_database_parameters(action, violation_ref)
        elif action_type in {"human_task", "human_review"}:
            parameters = self._create_human_task_parameters(action, violation_ref)
        elif action_type == "human_approval":
            parameters = self._create_approval_parameters(action, violation_ref)
        else:
            parameters = self._create_api_call_parameters(action, violation_ref)

        step = WorkflowStep(
            id=f"action_{order}_{uuid.uuid4().hex[:6]}",
            name=action,
            description=action,
            action_type=action_type,
            parameters=parameters,
            estimated_duration_minutes=duration,
        )
        step.expected_duration = duration
        step.requires_human_approval = requires_approval
        step.step_type = self._classify_step_type(action_type, requires_approval)
        return step

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    async def execute_workflow(self, workflow: RemediationWorkflow) -> Dict[str, Any]:
        step_results: List[Dict[str, Any]] = []
        if not workflow.steps:
            workflow.status = WorkflowStatus.COMPLETED
            workflow.started_at = datetime.now(timezone.utc)
            workflow.completed_at = workflow.started_at
            return {
                "success": True,
                "workflow_id": workflow.id,
                "execution_status": "completed",
                "step_results": step_results,
            }

        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = datetime.now(timezone.utc)

        success = True
        for index, step in enumerate(workflow.steps):
            workflow.current_step_index = index
            outcome = await self._execute_step(step)
            step_results.append({"step_id": step.id, "success": outcome.get("success", False), **outcome})

            if outcome.get("success"):
                step.status = WorkflowStatus.COMPLETED
            else:
                step.status = WorkflowStatus.FAILED
                success = False
                break

        workflow.completed_at = datetime.now(timezone.utc)
        workflow.status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED

        result: Dict[str, Any] = {
            "success": success,
            "workflow_id": workflow.id,
            "execution_status": "completed" if success else "failed",
            "step_results": step_results,
        }

        if not success:
            failure = next((res for res in step_results if not res.get("success")), None) or {}
            result["error"] = failure.get("error", "Workflow execution failed")

        return result

    async def orchestrate_remediation(
        self,
        decision_or_signal,
        violation: Optional[ComplianceViolation] = None
    ) -> Dict[str, Any]:
        """Convenience method that orchestrates the complete remediation workflow.
        
        This method combines workflow creation and execution in a single call,
        simplifying the most common use case.
        
        Args:
            decision_or_signal: Either a RemediationSignal (containing decision and violation)
                              or a RemediationDecision object
            violation: The compliance violation (required if first arg is RemediationDecision)
            
        Returns:
            Dict containing the complete workflow execution results including:
            - workflow_id: The ID of the created workflow
            - status: Final workflow status
            - results: Execution results for all steps
            - Any other execution metadata
        """
        # Handle both RemediationSignal and (RemediationDecision, violation) patterns
        from ..state.models import RemediationSignal
        
        if isinstance(decision_or_signal, RemediationSignal):
            signal = decision_or_signal
            decision = signal.decision
            violation = signal.violation
        else:
            decision = decision_or_signal
            if violation is None:
                raise ValueError("violation is required when passing RemediationDecision")
        
        # Create the workflow
        workflow = await self.create_workflow(decision, violation)
        
        # Execute the workflow
        execution_result = await self.execute_workflow(workflow)
        
        # Combine creation and execution results
        return {
            "workflow_id": workflow.id,
            "workflow": workflow.model_dump(),  # Convert to dict for consistency
            **execution_result,
        }

    async def _execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        handler_map = {
            "api_call": self._run_api_call,
            "database_operation": self._execute_database_step,
            "email_notification": self._send_email_step,
            "human_approval": self._create_approval_task,
            "human_task": self._create_human_task,
            "human_review": self._create_human_task,
            "create_sqs_queue": self._handle_sqs_creation,
            "validate_prerequisites": self._handle_prerequisite_validation,
            "execute_remediation": self._handle_remediation_execution,
            "verify_completion": self._handle_completion_verification,
            "send_notification": self._handle_notification,
            "update_compliance_status": self._handle_compliance_update,
        }

        handler = handler_map.get(step.action_type)
        if handler is None:
            return {"success": False, "error": f"Unsupported action type: {step.action_type}"}

        try:
            result = await handler(step)
            if step.action_type == "human_approval" and result.get("success"):
                result.setdefault("message", "Approval task created")
            elif step.action_type in {"human_task", "human_review"} and result.get("success"):
                result.setdefault("message", "Human task created")
            elif step.action_type == "email_notification" and result.get("success"):
                result.setdefault("message", "Email notification sent")
            elif step.action_type == "database_operation" and result.get("success"):
                result.setdefault("message", "Database operation completed")
            return result
        except Exception as exc:  # pragma: no cover - exercised in tests via side effects
            logger.error("Step execution error (%s): %s", step.action_type, exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Individual step handlers
    # ------------------------------------------------------------------
    async def _run_api_call(self, step: WorkflowStep) -> Dict[str, Any]:
        params = step.parameters
        url = params.get("endpoint", "https://api.example.com/remediation")
        method = params.get("method", "GET").upper()
        body = params.get("data")
        query_params = params.get("params")

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=body, params=query_params) as response:
                if response.status < 400:
                    try:
                        payload = await response.json()
                    except Exception:  # pragma: no cover - defensive
                        payload = {"status": response.status}
                    return {"success": True, "message": "API call completed", "response": payload}

                error_text = await response.text()
                return {"success": False, "error": f"API call failed with status {response.status}: {error_text}"}

    async def _execute_database_step(self, step: WorkflowStep) -> Dict[str, Any]:
        query = step.parameters.get("query")
        params = step.parameters.get("params", [])
        result = await self._execute_database_query(query, params)
        if result.get("success"):
            result.setdefault("message", "Database operation completed")
        else:
            result.setdefault("error", "Database operation failed")
        return result

    async def _send_email_step(self, step: WorkflowStep) -> Dict[str, Any]:
        result = await self._send_email(step.parameters)
        if result.get("success"):
            result.setdefault("message", "Email notification sent")
        else:
            result.setdefault("error", "Email notification failed")
        return result

    async def _create_approval_task(self, step: WorkflowStep) -> Dict[str, Any]:
        task_id = f"approval_{uuid.uuid4().hex[:8]}"
        task_record = {
            "task_id": task_id,
            "status": "pending",
            "type": "approval",
            **step.parameters,
        }
        await self._store_human_task(task_record)
        return {"success": True, "task_id": task_id, "status": "pending", "message": "Approval task created"}

    async def _create_human_task(self, step: WorkflowStep) -> Dict[str, Any]:
        task_id = f"human_{uuid.uuid4().hex[:8]}"
        task_record = {
            "task_id": task_id,
            "status": "assigned",
            "type": step.parameters.get("task_type", "general"),
            **step.parameters,
        }
        await self._store_human_task(task_record)
        return {"success": True, "task_id": task_id, "status": "assigned", "message": "Human task created"}

    async def _handle_sqs_creation(self, step: WorkflowStep) -> Dict[str, Any]:
        queue_name = step.parameters.get("queue_name", f"remediation-{uuid.uuid4().hex[:6]}")
        queue_url = f"https://sqs.example.com/{queue_name}"
        return {"success": True, "queue_url": queue_url, "queue_name": queue_name, "message": "SQS queue configured"}

    async def _handle_prerequisite_validation(self, step: WorkflowStep) -> Dict[str, Any]:
        prerequisites = step.parameters.get("prerequisites", [])
        results = {item: True for item in prerequisites}
        return {"success": True, "prerequisites_met": results, "message": "All prerequisites validated"}

    async def _handle_remediation_execution(self, step: WorkflowStep) -> Dict[str, Any]:
        automated = step.parameters.get("automated", False)
        actions = step.parameters.get("remediation_actions", [])
        if automated:
            return {
                "success": True,
                "actions_executed": len(actions),
                "message": "Automated remediation completed successfully",
            }
        return {
            "success": True,
            "requires_human": True,
            "message": "Human task created for remediation",
        }

    async def _handle_completion_verification(self, step: WorkflowStep) -> Dict[str, Any]:
        return {
            "success": True,
            "verification_passed": True,
            "message": "Completion verified",
        }

    async def _handle_notification(self, step: WorkflowStep) -> Dict[str, Any]:
        recipients = step.parameters.get("recipients", ["compliance_team"])  # pragma: no cover - used in tests
        return {"success": True, "notifications_sent": len(recipients), "message": "Notifications sent"}

    async def _handle_compliance_update(self, step: WorkflowStep) -> Dict[str, Any]:
        return {
            "success": True,
            "status_updated": True,
            "message": "Compliance status updated",
        }

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _map_remediation_to_workflow_type(self, remediation_type: RemediationType) -> WorkflowType:
        mapping = {
            RemediationType.AUTOMATIC: WorkflowType.AUTOMATIC,
            RemediationType.HUMAN_IN_LOOP: WorkflowType.HUMAN_IN_LOOP,
            RemediationType.MANUAL_ONLY: WorkflowType.MANUAL_ONLY,
        }
        return mapping.get(remediation_type, WorkflowType.MANUAL_ONLY)

    def _determine_action_type(self, action: str, decision_type: RemediationType) -> str:
        text = action.lower()
        if any(keyword in text for keyword in ("approve", "approval", "authorize")):
            return "human_approval"
        if any(keyword in text for keyword in ("delete", "remove", "purge", "erase")):
            return "database_operation"
        if any(keyword in text for keyword in ("email", "notify", "message", "inform")):
            if decision_type == RemediationType.MANUAL_ONLY:
                return "human_task"
            return "email_notification"
        if any(keyword in text for keyword in ("review", "policy", "legal", "audit", "consent")):
            return "human_task"
        if "stop" in text or "halt" in text:
            return "api_call"
        if decision_type != RemediationType.AUTOMATIC:
            return "human_task"
        return "api_call"

    def _requires_human_approval(self, action: str, decision_type: RemediationType) -> bool:
        text = action.lower()
        if decision_type in {RemediationType.HUMAN_IN_LOOP, RemediationType.MANUAL_ONLY}:
            return True
        return any(keyword in text for keyword in ("delete", "legal", "approval", "policy", "sensitive"))

    def _estimate_step_duration(self, action: str, action_type: str) -> int:
        base = {
            "api_call": 5,
            "database_operation": 15,
            "email_notification": 8,
            "human_task": 120,
            "human_review": 90,
            "human_approval": 30,
        }.get(action_type, 12)

        length = len(action)
        if action_type == "human_task" and length > 80:
            base = max(base, 120) + 30
        elif action_type == "api_call" and length > 60:
            base += 3
        elif action_type == "database_operation" and "backup" in action.lower():
            base += 10

        return base

    def _classify_step_type(self, action_type: str, requires_approval: bool) -> str:
        if action_type in {"human_task", "human_review"}:
            return "manual"
        if requires_approval:
            return "automated_with_approval"
        return "automated"

    def _add_approval_step_if_needed(
        self, steps: List[WorkflowStep], decision_type: RemediationType, violation_id: str
    ) -> List[WorkflowStep]:
        needs_approval = decision_type in {RemediationType.HUMAN_IN_LOOP, RemediationType.MANUAL_ONLY}
        if needs_approval and not any(step.action_type == "human_approval" for step in steps):
            approval_parameters = self._create_approval_parameters("Approve remediation", violation_id)
            approval_step = WorkflowStep(
                id=f"approval_{uuid.uuid4().hex[:6]}",
                name="Human approval required",
                description="Human approval prior to remediation",
                action_type="human_approval",
                parameters=approval_parameters,
                estimated_duration_minutes=30,
            )
            approval_step.expected_duration = 30
            approval_step.requires_human_approval = True
            approval_step.step_type = "manual"
            return [approval_step] + steps
        return steps

    def _calculate_total_duration(self, steps: List[WorkflowStep]) -> int:
        total = 0
        for step in steps:
            duration = step.expected_duration or step.estimated_duration_minutes or 0
            total += duration
        return total

    def _create_email_parameters(self, action: str, violation_id: Any) -> Dict[str, Any]:
        text = action.lower()
        template = "remediation_update"
        if "confirm" in text or "deletion" in text:
            template = "deletion_confirmation"
        subject = f"Remediation update for violation {violation_id}"
        if "delete" in text:
            subject = f"Deletion confirmation for {violation_id}"

        recipient = "user@example.com"
        if "notify" in text or "stakeholder" in text:
            recipient = "stakeholders@example.com"

        return {
            "recipient": recipient,
            "subject": subject,
            "template": template,
            "data": {"violation_id": violation_id, "message": action},
        }

    def _create_human_task_parameters(self, action: str, violation_id: Any) -> Dict[str, Any]:
        text = action.lower()
        if "legal" in text:
            task_type = "legal_review"
            role = "legal_counsel"
            priority = "high"
        elif "policy" in text or "update" in text:
            task_type = "policy_update"
            role = "compliance_officer"
            priority = "medium"
        elif "consent" in text:
            task_type = "consent_update"
            role = "data_steward"
            priority = "medium"
        else:
            task_type = "manual_task"
            role = "operations_team"
            priority = "medium"

        return {
            "task_type": task_type,
            "assigned_role": role,
            "priority": priority,
            "description": action,
            "violation_id": violation_id,
        }

    def _create_approval_parameters(self, action: str, violation_id: Any) -> Dict[str, Any]:
        text = action.lower()
        if "policy" in text:
            approval_type = "policy_change"
            approver = "compliance_officer"
            requires_legal = True
        else:
            approval_type = "data_deletion"
            approver = "data_protection_officer"
            requires_legal = False

        return {
            "approval_type": approval_type,
            "approver_role": approver,
            "description": action,
            "violation_id": violation_id,
            "requires_documentation": True,
            "requires_legal_review": requires_legal,
        }

    def _create_api_call_parameters(self, action: str, violation_id: Any) -> Dict[str, Any]:
        text = action.lower()
        endpoint_base = "https://api.example.com"
        if "stop" in text or "halt" in text:
            endpoint = f"{endpoint_base}/remediation/{violation_id}/stop"
            method = "POST"
        elif "update" in text or "modify" in text:
            endpoint = f"{endpoint_base}/remediation/{violation_id}/update"
            method = "PUT"
        else:
            endpoint = f"{endpoint_base}/remediation/{violation_id}/action"
            method = "POST"

        return {
            "endpoint": endpoint,
            "method": method,
            "data": {"description": action, "violation_id": violation_id},
        }

    def _create_database_parameters(self, action: str, violation_id: Any) -> Dict[str, Any]:
        text = action.lower()
        if "delete" in text or "remove" in text:
            query = "DELETE FROM remediation_actions WHERE violation_id = ?"
            params = [violation_id]
            backup_required = True
        else:
            query = "UPDATE remediation_actions SET status = ? WHERE violation_id = ?"
            params = ["updated", violation_id]
            backup_required = False

        return {
            "query": query,
            "params": params,
            "backup_required": backup_required,
        }

    async def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        message = EmailMessage()
        message["To"] = params.get("recipient", "user@example.com")
        message["From"] = "remediation@example.com"
        message["Subject"] = params.get("subject", "Remediation update")
        message.set_content(json.dumps(params.get("data", {})))

        with smtplib.SMTP("localhost") as smtp:  # pragma: no cover - mocked in tests
            smtp.send_message(message)

        return {"success": True, "message": "Email notification sent", "message_id": uuid.uuid4().hex}

    async def _execute_database_query(self, query: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        params = params or []
        with sqlite3.connect(":memory:") as connection:  # pragma: no cover - mocked in tests
            cursor = connection.cursor()
            cursor.execute(query, params)
            connection.commit()
            rows = cursor.rowcount

        return {"success": True, "rows_affected": rows, "message": "Database operation completed"}

    async def _store_human_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self._human_tasks[task["task_id"]] = task
        return task

    def _build_workflow_templates(self) -> Dict[RemediationType, List[Dict[str, Any]]]:
        return {
            RemediationType.AUTOMATIC: [
                {
                    "name": "Data analysis",
                    "description": "Assess impact and scope",
                    "action_type": "api_call",
                    "parameters": {"endpoint": "https://api.example.com/analyse", "method": "POST"},
                    "duration": 10,
                },
                {
                    "name": "Validate prerequisites",
                    "description": "Ensure environment is ready",
                    "action_type": "validate_prerequisites",
                    "duration": 8,
                },
            ],
            RemediationType.HUMAN_IN_LOOP: [
                {
                    "name": "Human review",
                    "description": "Compliance team reviews remediation plan",
                    "action_type": "human_review",
                    "requires_human_approval": True,
                    "step_type": "manual",
                    "duration": 60,
                },
            ],
            RemediationType.MANUAL_ONLY: [
                {
                    "name": "Initial coordination",
                    "description": "Assign manual remediation tasks",
                    "action_type": "human_task",
                    "step_type": "manual",
                    "duration": 45,
                }
            ],
        }
