"""
Workflow Agent for remediation execution management

This agent creates and manages remediation workflows, including orchestrating
automated steps and human intervention points.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
import uuid

from ..state.models import (
    RemediationSignal,
    RemediationDecision,
    RemediationWorkflow,
    WorkflowStep,
    WorkflowStatus,
    WorkflowType,
    RemediationType
)

logger = logging.getLogger(__name__)


class WorkflowAgent:
    """
    Agent responsible for creating and managing remediation workflows,
    including both automated and human-supervised processes.
    """

    def __init__(self) -> None:
        # Workflow templates for different remediation types
        self.workflow_templates = {
            RemediationType.AUTOMATIC: self._get_automatic_workflow_template(),
            RemediationType.HUMAN_IN_LOOP: self._get_human_loop_workflow_template(),
            RemediationType.MANUAL_ONLY: self._get_manual_workflow_template()
        }

        # Step execution handlers
        self.step_handlers = {
            "data_analysis": self._handle_data_analysis,
            "create_sqs_queue": self._handle_sqs_creation,
            "validate_prerequisites": self._handle_prerequisite_validation,
            "execute_remediation": self._handle_remediation_execution,
            "verify_completion": self._handle_completion_verification,
            "human_review": self._handle_human_review,
            "send_notification": self._handle_notification,
            "update_compliance_status": self._handle_compliance_update
        }

    async def create_workflow(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision,
        feasibility_details: Dict[str, Any]
    ) -> RemediationWorkflow:
        """
        Create a remediation workflow based on the decision and feasibility analysis

        Args:
            signal: The remediation signal
            decision: The remediation decision
            feasibility_details: Output from ValidationAgent

        Returns:
            RemediationWorkflow configured for execution
        """
        logger.info(f"Creating workflow for {signal.violation.rule_id} with type {decision.remediation_type}")

        try:
            # Create base workflow
            workflow = RemediationWorkflow(
                id=f"workflow_{uuid.uuid4().hex[:8]}",
                violation_id=signal.violation.rule_id,
                activity_id=signal.violation.activity_id,
                remediation_type=decision.remediation_type,
                workflow_type=self._map_remediation_to_workflow_type(decision.remediation_type),
                priority=signal.urgency,
                metadata={
                    "framework": signal.framework,
                    "violation_description": signal.violation.description,
                    "remediation_actions": signal.violation.remediation_actions,
                    "decision_confidence": decision.confidence_score,
                    "feasibility_score": feasibility_details.get("feasibility_score", 0.0),
                    "estimated_effort": decision.estimated_effort
                }
            )

            # Generate workflow steps based on remediation type
            steps = await self._generate_workflow_steps(
                signal, decision, feasibility_details
            )

            workflow.steps = steps

            logger.info(f"Workflow created with {len(steps)} steps")
            return workflow

        except Exception as e:
            logger.error(f"Error creating workflow: {str(e)}")
            raise

    async def _generate_workflow_steps(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision,
        feasibility_details: Dict[str, Any]
    ) -> List[WorkflowStep]:
        """Generate workflow steps based on remediation type and requirements"""

        template = self.workflow_templates[decision.remediation_type]
        steps = []

        for step_config in template:
            step = WorkflowStep(
                id=f"step_{len(steps) + 1}_{uuid.uuid4().hex[:6]}",
                name=step_config["name"],
                description=step_config["description"],
                action_type=step_config["action_type"],
                parameters=await self._customize_step_parameters(
                    step_config, signal, decision, feasibility_details
                )
            )
            steps.append(step)

        # Add remediation-specific steps
        remediation_steps = await self._create_remediation_specific_steps(
            signal, decision, feasibility_details
        )
        steps.extend(remediation_steps)

        return steps

    async def _customize_step_parameters(
        self,
        step_config: Dict[str, Any],
        signal: RemediationSignal,
        decision: RemediationDecision,
        feasibility_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Customize step parameters based on specific remediation requirements"""

        base_params = step_config.get("parameters", {}).copy()

        # Add signal-specific parameters
        base_params.update({
            "violation_id": signal.violation.rule_id,
            "activity_id": signal.violation.activity_id,
            "framework": signal.framework,
            "urgency": signal.urgency.value,
            "data_types": [dt.value for dt in signal.activity.data_types]
        })

        # Customize based on step type
        if step_config["action_type"] == "create_sqs_queue":
            base_params.update({
                "queue_name": f"remediation-{signal.violation.rule_id}",
                "visibility_timeout": 300,
                "message_retention": 1209600,  # 14 days
                "dead_letter_queue": True
            })

        elif step_config["action_type"] == "human_review":
            base_params.update({
                "assignee": "compliance_team",
                "due_date": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                "priority": signal.urgency.value,
                "review_items": decision.prerequisites
            })

        elif step_config["action_type"] == "execute_remediation":
            base_params.update({
                "remediation_actions": signal.violation.remediation_actions,
                "validation_required": decision.remediation_type != RemediationType.AUTOMATIC,
                "rollback_plan": True
            })

        return base_params

    async def _create_remediation_specific_steps(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision,
        feasibility_details: Dict[str, Any]
    ) -> List[WorkflowStep]:
        """Create steps specific to the remediation actions required"""

        specific_steps = []

        # Analyze each remediation action and create appropriate steps
        for i, action in enumerate(signal.violation.remediation_actions):
            action_type = self._determine_action_type(action)

            step = WorkflowStep(
                id=f"remediation_action_{i + 1}_{uuid.uuid4().hex[:6]}",
                name=f"Execute: {action[:50]}...",
                description=f"Execute remediation action: {action}",
                action_type=action_type,
                parameters={
                    "action_text": action,
                    "automated": decision.remediation_type == RemediationType.AUTOMATIC,
                    "requires_approval": decision.remediation_type == RemediationType.HUMAN_IN_LOOP,
                    "data_types": [dt.value for dt in signal.activity.data_types],
                    "cross_border": signal.activity.cross_border_transfers
                }
            )
            specific_steps.append(step)

        return specific_steps

    def _determine_action_type(self, action: str) -> str:
        """Determine the action type based on the remediation action text"""
        action_lower = action.lower()

        if any(word in action_lower for word in ["delete", "remove", "purge"]):
            return "data_deletion"
        elif any(word in action_lower for word in ["update", "modify", "correct"]):
            return "data_modification"
        elif any(word in action_lower for word in ["encrypt", "secure", "protect"]):
            return "data_protection"
        elif any(word in action_lower for word in ["notify", "inform", "contact"]):
            return "notification"
        elif any(word in action_lower for word in ["consent", "withdraw", "opt-out"]):
            return "consent_management"
        elif any(word in action_lower for word in ["transfer", "export", "migrate"]):
            return "data_transfer"
        else:
            return "generic_action"

    def _map_remediation_to_workflow_type(self, remediation_type: RemediationType) -> WorkflowType:
        """Map RemediationType to WorkflowType"""
        mapping = {
            RemediationType.AUTOMATIC: WorkflowType.AUTOMATIC,
            RemediationType.HUMAN_IN_LOOP: WorkflowType.HUMAN_IN_LOOP,
            RemediationType.MANUAL_ONLY: WorkflowType.MANUAL_ONLY
        }
        return mapping.get(remediation_type, WorkflowType.MANUAL_ONLY)

    async def execute_workflow_step(
        self,
        workflow: RemediationWorkflow,
        step_id: str
    ) -> Dict[str, Any]:
        """
        Execute a specific workflow step

        Args:
            workflow: The workflow containing the step
            step_id: ID of the step to execute

        Returns:
            Execution result dictionary
        """
        step = next((s for s in workflow.steps if s.id == step_id), None)
        if not step:
            raise ValueError(f"Step {step_id} not found in workflow {workflow.id}")

        logger.info(f"Executing step {step.name} for workflow {workflow.id}")

        try:
            step.status = WorkflowStatus.IN_PROGRESS

            # Get the appropriate handler
            handler = self.step_handlers.get(step.action_type)
            if not handler:
                raise ValueError(f"No handler found for action type: {step.action_type}")

            # Execute the step
            result = await handler(step, workflow)

            # Update step status based on result
            if result.get("success", False):
                step.status = WorkflowStatus.COMPLETED
            else:
                step.status = WorkflowStatus.FAILED
                step.error_message = result.get("error", "Step execution failed")

            return result

        except Exception as e:
            step.status = WorkflowStatus.FAILED
            step.error_message = str(e)
            step.retry_count += 1

            logger.error(f"Error executing step {step.name}: {str(e)}")
            return {"success": False, "error": str(e)}

    # Step handler methods
    async def _handle_data_analysis(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle data analysis step"""
        # In production, this would perform actual data analysis
        return {
            "success": True,
            "data_analysis": {
                "records_found": 1250,
                "data_locations": ["primary_db", "backup_storage"],
                "estimated_time": 45
            }
        }

    async def _handle_sqs_creation(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle SQS queue creation step"""
        # This would use the SQS tool in production
        queue_name = step.parameters.get("queue_name", f"remediation-{workflow.id}")

        # Simulate SQS queue creation
        queue_url = f"https://sqs.region.amazonaws.com/account/{queue_name}"

        return {
            "success": True,
            "queue_url": queue_url,
            "queue_name": queue_name,
            "message": f"SQS queue {queue_name} created successfully"
        }

    async def _handle_prerequisite_validation(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle prerequisite validation step"""
        prerequisites = step.parameters.get("prerequisites", [])

        # In production, this would validate actual prerequisites
        validation_results = {}
        all_met = True

        for prereq in prerequisites:
            # Simulate prerequisite checking
            is_met = True  # Would be actual validation logic
            validation_results[prereq] = is_met
            if not is_met:
                all_met = False

        return {
            "success": all_met,
            "prerequisites_met": validation_results,
            "message": "All prerequisites validated" if all_met else "Some prerequisites not met"
        }

    async def _handle_remediation_execution(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle actual remediation execution step"""
        actions = step.parameters.get("remediation_actions", [])
        automated = step.parameters.get("automated", False)

        if automated:
            # Execute automated remediation
            return {
                "success": True,
                "actions_executed": len(actions),
                "execution_time": 120,
                "message": "Automated remediation completed successfully"
            }
        else:
            # Create human task for manual execution
            return {
                "success": True,
                "requires_human": True,
                "human_task_created": True,
                "message": "Human task created for manual remediation"
            }

    async def _handle_completion_verification(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle completion verification step"""
        # In production, this would verify that remediation was actually completed
        return {
            "success": True,
            "verification_passed": True,
            "compliance_status": "resolved",
            "message": "Remediation completion verified"
        }

    async def _handle_human_review(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle human review step"""
        # Create human task
        task_id = f"review_{uuid.uuid4().hex[:8]}"

        return {
            "success": True,
            "human_task_id": task_id,
            "assignee": step.parameters.get("assignee", "compliance_team"),
            "due_date": step.parameters.get("due_date"),
            "message": f"Human review task {task_id} created"
        }

    async def _handle_notification(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle notification step"""
        # In production, this would send actual notifications
        return {
            "success": True,
            "notifications_sent": 1,
            "recipients": ["compliance_team", "data_protection_officer"],
            "message": "Notifications sent successfully"
        }

    async def _handle_compliance_update(
        self,
        step: WorkflowStep,
        workflow: RemediationWorkflow
    ) -> Dict[str, Any]:
        """Handle compliance status update step"""
        # In production, this would update the compliance system
        return {
            "success": True,
            "status_updated": True,
            "new_status": "remediated",
            "message": "Compliance status updated successfully"
        }

    # Workflow templates
    def _get_automatic_workflow_template(self) -> List[Dict[str, Any]]:
        """Get workflow template for automatic remediation"""
        return [
            {
                "name": "Data Analysis",
                "description": "Analyze data to understand scope of remediation",
                "action_type": "data_analysis",
                "parameters": {}
            },
            {
                "name": "Create SQS Queue",
                "description": "Create AWS SQS queue for workflow management",
                "action_type": "create_sqs_queue",
                "parameters": {}
            },
            {
                "name": "Validate Prerequisites",
                "description": "Validate all prerequisites are met",
                "action_type": "validate_prerequisites",
                "parameters": {}
            },
            {
                "name": "Execute Remediation",
                "description": "Execute automated remediation actions",
                "action_type": "execute_remediation",
                "parameters": {"automated": True}
            },
            {
                "name": "Verify Completion",
                "description": "Verify remediation was completed successfully",
                "action_type": "verify_completion",
                "parameters": {}
            },
            {
                "name": "Update Compliance Status",
                "description": "Update compliance system with resolution",
                "action_type": "update_compliance_status",
                "parameters": {}
            }
        ]

    def _get_human_loop_workflow_template(self) -> List[Dict[str, Any]]:
        """Get workflow template for human-in-the-loop remediation"""
        return [
            {
                "name": "Create SQS Queue",
                "description": "Create AWS SQS queue for workflow management",
                "action_type": "create_sqs_queue",
                "parameters": {}
            },
            {
                "name": "Human Review",
                "description": "Human review of remediation plan",
                "action_type": "human_review",
                "parameters": {}
            },
            {
                "name": "Execute Remediation",
                "description": "Execute remediation with human oversight",
                "action_type": "execute_remediation",
                "parameters": {"automated": False, "requires_approval": True}
            },
            {
                "name": "Verify Completion",
                "description": "Human verification of remediation completion",
                "action_type": "verify_completion",
                "parameters": {"human_verification": True}
            },
            {
                "name": "Send Notifications",
                "description": "Notify stakeholders of completion",
                "action_type": "send_notification",
                "parameters": {}
            },
            {
                "name": "Update Compliance Status",
                "description": "Update compliance system with resolution",
                "action_type": "update_compliance_status",
                "parameters": {}
            }
        ]

    def _get_manual_workflow_template(self) -> List[Dict[str, Any]]:
        """Get workflow template for manual-only remediation"""
        return [
            {
                "name": "Create SQS Queue",
                "description": "Create AWS SQS queue for task management",
                "action_type": "create_sqs_queue",
                "parameters": {}
            },
            {
                "name": "Create Human Tasks",
                "description": "Create detailed human tasks for manual remediation",
                "action_type": "human_review",
                "parameters": {"task_type": "manual_remediation"}
            },
            {
                "name": "Send Notifications",
                "description": "Notify assigned personnel",
                "action_type": "send_notification",
                "parameters": {"urgency": "high"}
            }
        ]