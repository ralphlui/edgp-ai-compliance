"""
Human Loop Node for LangGraph remediation workflow

This node manages human-in-the-loop workflows, including task creation,
notifications, and human intervention coordination.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta, timezone

from ...tools.notification_tool import NotificationTool, NotificationType
from ...state.remediation_state import RemediationStateSchema
from ...state.models import (
    HumanTask,
    WorkflowStatus,
    RemediationType,
    RiskLevel
)

logger = logging.getLogger(__name__)


class HumanLoopNode:
    """
    LangGraph node for managing human intervention in remediation workflows
    """

    def __init__(self):
        self.notification_tool = NotificationTool()

        # Human task templates based on remediation type and complexity
        self.task_templates = {
            RemediationType.HUMAN_IN_LOOP: {
                "title": "Review and Approve Remediation Plan",
                "description": "Review the proposed remediation plan and approve execution",
                "default_duration_hours": 24
            },
            RemediationType.MANUAL_ONLY: {
                "title": "Manual Remediation Required",
                "description": "Perform manual remediation for compliance violation",
                "default_duration_hours": 48
            }
        }

    async def __call__(self, state: RemediationStateSchema) -> RemediationStateSchema:
        """
        Execute the human loop node

        Args:
            state: Current remediation state

        Returns:
            Updated state with human tasks and notifications
        """
        logger.info(f"Executing human loop node for violation {state['signal'].violation.rule_id}")

        try:
            # Add to execution path
            state["execution_path"].append("human_loop_started")

            # Determine the type of human intervention needed
            intervention_type = self._determine_intervention_type(state)

            # Create appropriate human tasks
            human_tasks = await self._create_human_tasks(state, intervention_type)

            # Send notifications
            notification_results = await self._send_notifications(state, human_tasks)

            # Schedule deadline reminders
            reminder_results = await self._schedule_reminders(human_tasks, state)

            # Update state
            state["human_task"] = human_tasks[0] if human_tasks else None
            state["requires_human"] = True

            state["context"].update({
                "human_tasks_created": len(human_tasks),
                "notifications_sent": len([r for r in notification_results if r.get("success")]),
                "reminders_scheduled": sum(r.get("total_scheduled", 0) for r in reminder_results),
                "intervention_type": intervention_type
            })

            state["execution_path"].append("human_loop_completed")

            logger.info(f"Human loop setup complete: {len(human_tasks)} tasks created, "
                       f"{len(notification_results)} notifications sent")

            return state

        except Exception as e:
            logger.error(f"Error in human loop node: {str(e)}")
            state["errors"].append(f"Human loop error: {str(e)}")
            state["execution_path"].append("human_loop_failed")
            return state

    def _determine_intervention_type(self, state: RemediationStateSchema) -> str:
        """Determine the type of human intervention needed"""

        decision = state.get("decision")
        if not decision:
            return "manual_review"

        complexity_assessment = state.get("complexity_assessment", {})
        overall_complexity = complexity_assessment.get("overall_complexity", 0.5)

        if decision.remediation_type == RemediationType.MANUAL_ONLY:
            return "full_manual_execution"
        elif decision.remediation_type == RemediationType.HUMAN_IN_LOOP:
            if overall_complexity > 0.7:
                return "complex_review_approval"
            else:
                return "standard_review_approval"
        else:
            return "oversight_only"

    async def _create_human_tasks(
        self,
        state: RemediationStateSchema,
        intervention_type: str
    ) -> list[HumanTask]:
        """Create human tasks based on intervention type and workflow requirements"""

        decision = state.get("decision")
        workflow = state.get("workflow")
        signal = state["signal"]

        tasks = []

        if intervention_type == "full_manual_execution":
            tasks.extend(await self._create_manual_execution_tasks(state))
        elif intervention_type in ["complex_review_approval", "standard_review_approval"]:
            tasks.extend(await self._create_review_approval_tasks(state, intervention_type))
        elif intervention_type == "oversight_only":
            tasks.extend(await self._create_oversight_tasks(state))

        # Add common tasks for high-risk violations
        if signal.violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            tasks.extend(await self._create_risk_management_tasks(state))

        return tasks

    async def _create_manual_execution_tasks(self, state: RemediationStateSchema) -> list[HumanTask]:
        """Create tasks for full manual execution"""

        signal = state["signal"]
        decision = state.get("decision")
        workflow = state.get("workflow")

        tasks = []

        # Main execution task
        main_task = HumanTask(
            id=f"manual_exec_{workflow.id}",
            workflow_id=workflow.id,
            title="Manual Remediation Execution",
            description=f"Manually execute remediation for violation: {signal.violation.description}",
            assignee=self._get_assignee_for_manual_task(signal),
            priority=signal.urgency,
            due_date=datetime.now(timezone.utc) + timedelta(hours=self._get_task_duration(signal.urgency)),
            instructions=self._create_manual_execution_instructions(signal, decision),
            required_approvals=self._get_required_approvals(signal)
        )

        tasks.append(main_task)

        # Documentation task
        doc_task = HumanTask(
            id=f"manual_doc_{workflow.id}",
            workflow_id=workflow.id,
            title="Document Manual Remediation",
            description="Document the manual remediation process and outcomes",
            assignee=main_task.assignee,
            priority=signal.urgency,
            due_date=main_task.due_date + timedelta(hours=2),
            instructions=[
                "Document all remediation actions taken",
                "Record any issues or complications encountered",
                "Verify compliance resolution",
                "Update compliance tracking systems"
            ]
        )

        tasks.append(doc_task)

        return tasks

    async def _create_review_approval_tasks(
        self,
        state: RemediationStateSchema,
        intervention_type: str
    ) -> list[HumanTask]:
        """Create review and approval tasks"""

        signal = state["signal"]
        decision = state.get("decision")
        workflow = state.get("workflow")

        tasks = []

        # Determine review complexity
        is_complex = intervention_type == "complex_review_approval"
        review_hours = 24 if is_complex else 8

        # Review task
        review_task = HumanTask(
            id=f"review_{workflow.id}",
            workflow_id=workflow.id,
            title="Review Remediation Plan" + (" (Complex)" if is_complex else ""),
            description=f"Review and validate proposed remediation plan for: {signal.violation.description}",
            assignee=self._get_assignee_for_review(signal, is_complex),
            priority=signal.urgency,
            due_date=datetime.now(timezone.utc) + timedelta(hours=review_hours),
            instructions=self._create_review_instructions(signal, decision, is_complex)
        )

        tasks.append(review_task)

        # Approval task (for high-risk items)
        if signal.violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] or is_complex:
            approval_task = HumanTask(
                id=f"approval_{workflow.id}",
                workflow_id=workflow.id,
                title="Approve Remediation Execution",
                description="Provide final approval for remediation execution",
                assignee=self._get_approver(signal),
                priority=signal.urgency,
                due_date=review_task.due_date + timedelta(hours=4),
                instructions=[
                    "Review the completed analysis and recommendations",
                    "Verify regulatory compliance of proposed actions",
                    "Assess business impact and risks",
                    "Provide approval or request modifications"
                ],
                required_approvals=["dpo_approval"] if signal.violation.risk_level == RiskLevel.CRITICAL else []
            )

            tasks.append(approval_task)

        return tasks

    async def _create_oversight_tasks(self, state: RemediationStateSchema) -> list[HumanTask]:
        """Create oversight tasks for monitoring automatic execution"""

        signal = state["signal"]
        workflow = state.get("workflow")

        oversight_task = HumanTask(
            id=f"oversight_{workflow.id}",
            workflow_id=workflow.id,
            title="Monitor Automated Remediation",
            description="Monitor and validate automated remediation execution",
            assignee=self._get_assignee_for_oversight(signal),
            priority=signal.urgency,
            due_date=datetime.now(timezone.utc) + timedelta(hours=4),
            instructions=[
                "Monitor automated remediation progress",
                "Verify successful completion of each step",
                "Intervene if issues arise",
                "Confirm final compliance resolution"
            ]
        )

        return [oversight_task]

    async def _create_risk_management_tasks(self, state: RemediationStateSchema) -> list[HumanTask]:
        """Create additional tasks for high-risk violations"""

        signal = state["signal"]
        workflow = state.get("workflow")

        tasks = []

        # Risk assessment task
        risk_task = HumanTask(
            id=f"risk_assess_{workflow.id}",
            workflow_id=workflow.id,
            title="Risk Assessment and Mitigation",
            description="Assess risks and develop mitigation strategies",
            assignee="risk_management_team",
            priority=signal.urgency,
            due_date=datetime.now(timezone.utc) + timedelta(hours=12),
            instructions=[
                "Assess potential impacts of remediation",
                "Identify any additional risks",
                "Develop mitigation strategies",
                "Consider regulatory notification requirements"
            ]
        )

        tasks.append(risk_task)

        # Stakeholder notification task (for critical violations)
        if signal.violation.risk_level == RiskLevel.CRITICAL:
            stakeholder_task = HumanTask(
                id=f"stakeholder_notify_{workflow.id}",
                workflow_id=workflow.id,
                title="Stakeholder Notification",
                description="Notify key stakeholders of critical violation remediation",
                assignee="compliance_manager",
                priority=signal.urgency,
                due_date=datetime.now(timezone.utc) + timedelta(hours=6),
                instructions=[
                    "Notify senior management",
                    "Prepare stakeholder communication",
                    "Consider regulatory notification requirements",
                    "Schedule follow-up meetings if necessary"
                ]
            )

            tasks.append(stakeholder_task)

        return tasks

    async def _send_notifications(
        self,
        state: RemediationStateSchema,
        human_tasks: list[HumanTask]
    ) -> list[Dict[str, Any]]:
        """Send notifications for human tasks"""

        workflow = state.get("workflow")
        results = []

        for task in human_tasks:
            try:
                # Determine notification type based on task priority and type
                notification_type = self._get_notification_type(task, state)

                # Send notification
                result = await self.notification_tool.send_human_task_notification(
                    task, workflow, notification_type
                )

                results.append(result)

                # Send urgent alerts for critical tasks
                if task.priority == RiskLevel.CRITICAL:
                    urgent_result = await self.notification_tool.send_urgent_alert(
                        workflow,
                        f"Critical human task created: {task.title}",
                        [f"Review and complete task: {task.id}"],
                        f"Due: {task.due_date.isoformat() if task.due_date else 'ASAP'}"
                    )
                    results.append(urgent_result)

            except Exception as e:
                logger.error(f"Error sending notification for task {task.id}: {str(e)}")
                results.append({"success": False, "error": str(e), "task_id": task.id})

        return results

    async def _schedule_reminders(
        self,
        human_tasks: list[HumanTask],
        state: RemediationStateSchema
    ) -> list[Dict[str, Any]]:
        """Schedule deadline reminders for human tasks"""

        workflow = state.get("workflow")
        results = []

        for task in human_tasks:
            try:
                # Determine reminder schedule based on task priority
                reminder_hours = self._get_reminder_schedule(task.priority)

                result = await self.notification_tool.schedule_deadline_reminders(
                    task, workflow, reminder_hours
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error scheduling reminders for task {task.id}: {str(e)}")
                results.append({"success": False, "error": str(e), "task_id": task.id})

        return results

    def _get_assignee_for_manual_task(self, signal) -> str:
        """Get appropriate assignee for manual execution tasks"""

        # Assign based on data types and complexity
        if any(dt.value in ["health_data", "biometric_data"] for dt in signal.activity.data_types):
            return "data_privacy_specialist"
        elif any(dt.value in ["financial_data"] for dt in signal.activity.data_types):
            return "financial_compliance_specialist"
        elif signal.violation.risk_level == RiskLevel.CRITICAL:
            return "senior_compliance_officer"
        else:
            return "compliance_team"

    def _get_assignee_for_review(self, signal, is_complex: bool) -> str:
        """Get appropriate assignee for review tasks"""

        if is_complex or signal.violation.risk_level == RiskLevel.CRITICAL:
            return "senior_compliance_officer"
        elif signal.violation.risk_level == RiskLevel.HIGH:
            return "compliance_manager"
        else:
            return "compliance_analyst"

    def _get_assignee_for_oversight(self, signal) -> str:
        """Get appropriate assignee for oversight tasks"""

        if signal.violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return "compliance_manager"
        else:
            return "compliance_analyst"

    def _get_approver(self, signal) -> str:
        """Get appropriate approver based on risk level"""

        if signal.violation.risk_level == RiskLevel.CRITICAL:
            return "dpo"  # Data Protection Officer
        elif signal.violation.risk_level == RiskLevel.HIGH:
            return "compliance_manager"
        else:
            return "senior_compliance_analyst"

    def _get_task_duration(self, urgency: RiskLevel) -> int:
        """Get task duration in hours based on urgency"""

        duration_map = {
            RiskLevel.CRITICAL: 8,   # 8 hours
            RiskLevel.HIGH: 24,      # 1 day
            RiskLevel.MEDIUM: 48,    # 2 days
            RiskLevel.LOW: 72        # 3 days
        }

        return duration_map.get(urgency, 24)

    def _create_manual_execution_instructions(self, signal, decision) -> list[str]:
        """Create detailed instructions for manual execution"""

        instructions = [
            f"Execute the following remediation actions: {', '.join(signal.violation.remediation_actions)}",
            f"Ensure compliance with {signal.framework} framework requirements",
            "Document all actions taken with timestamps",
            "Verify data integrity before and after remediation"
        ]

        # Add data-type specific instructions
        if any(dt.value in ["health_data", "biometric_data"] for dt in signal.activity.data_types):
            instructions.append("Follow special procedures for sensitive health/biometric data")

        if signal.activity.cross_border_transfers:
            instructions.append("Consider cross-border transfer restrictions and requirements")

        if decision and decision.prerequisites:
            instructions.append(f"Complete prerequisites: {', '.join(decision.prerequisites)}")

        return instructions

    def _create_review_instructions(self, signal, decision, is_complex: bool) -> list[str]:
        """Create review instructions based on complexity"""

        base_instructions = [
            "Review the proposed remediation plan for completeness and accuracy",
            "Verify compliance with applicable regulations",
            "Assess potential business impact",
            "Check for any missing steps or considerations"
        ]

        if is_complex:
            base_instructions.extend([
                "Perform detailed technical feasibility analysis",
                "Consult with technical teams if necessary",
                "Consider alternative remediation approaches",
                "Document detailed review findings"
            ])

        if signal.violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            base_instructions.extend([
                "Assess regulatory notification requirements",
                "Consider stakeholder communication needs",
                "Evaluate timeline and resource requirements"
            ])

        return base_instructions

    def _get_required_approvals(self, signal) -> list[str]:
        """Get required approvals based on signal characteristics"""

        approvals = []

        if signal.violation.risk_level == RiskLevel.CRITICAL:
            approvals.extend(["dpo_approval", "senior_management_approval"])
        elif signal.violation.risk_level == RiskLevel.HIGH:
            approvals.append("manager_approval")

        if any(dt.value in ["health_data", "biometric_data"] for dt in signal.activity.data_types):
            approvals.append("privacy_specialist_approval")

        if signal.activity.cross_border_transfers:
            approvals.append("international_compliance_approval")

        return approvals

    def _get_notification_type(self, task: HumanTask, state: RemediationStateSchema) -> NotificationType:
        """Determine appropriate notification type for a task"""

        if task.priority == RiskLevel.CRITICAL:
            return NotificationType.URGENT_ATTENTION
        elif "approval" in task.title.lower():
            return NotificationType.APPROVAL_NEEDED
        else:
            return NotificationType.HUMAN_INTERVENTION_REQUIRED

    def _get_reminder_schedule(self, priority: RiskLevel) -> list[int]:
        """Get reminder schedule based on priority"""

        reminder_schedules = {
            RiskLevel.CRITICAL: [4, 1],      # 4 hours, 1 hour before
            RiskLevel.HIGH: [24, 4, 1],      # 24 hours, 4 hours, 1 hour before
            RiskLevel.MEDIUM: [48, 24, 4],   # 48 hours, 24 hours, 4 hours before
            RiskLevel.LOW: [72, 24]          # 72 hours, 24 hours before
        }

        return reminder_schedules.get(priority, [24, 4])

    def is_human_intervention_complete(self, state: RemediationStateSchema) -> bool:
        """Check if human intervention is complete"""

        human_task = state.get("human_task")
        if not human_task:
            return True

        return human_task.status == WorkflowStatus.COMPLETED

    def get_human_loop_summary(self, state: RemediationStateSchema) -> Dict[str, Any]:
        """Get summary of human loop activities"""

        context = state.get("context", {})
        human_task = state.get("human_task")

        summary = {
            "human_tasks_created": context.get("human_tasks_created", 0),
            "notifications_sent": context.get("notifications_sent", 0),
            "reminders_scheduled": context.get("reminders_scheduled", 0),
            "intervention_type": context.get("intervention_type", "unknown"),
            "requires_human": state.get("requires_human", False)
        }

        if human_task:
            summary["primary_task"] = {
                "id": human_task.id,
                "title": human_task.title,
                "assignee": human_task.assignee,
                "priority": human_task.priority.value,
                "due_date": human_task.due_date.isoformat() if human_task.due_date else None,
                "status": human_task.status.value,
                "created_at": human_task.created_at.isoformat()
            }

        return summary
