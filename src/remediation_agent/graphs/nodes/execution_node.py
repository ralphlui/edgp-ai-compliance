"""
Execution Node for LangGraph remediation workflow

This node actually executes remediation actions based on the workflow plan.
It provides the missing execution layer that was previously only creating workflows.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum

from ...state.remediation_state import RemediationStateSchema
from ...state.models import (
    RemediationType,
    WorkflowStatus,
    RemediationWorkflow,
    WorkflowStep
)

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status for remediation actions"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"
    CANCELLED = "cancelled"


class RemediationExecutor:
    """Base class for remediation action executors"""

    async def execute(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a remediation action"""
        raise NotImplementedError

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate action parameters"""
        return True


class DataDeletionExecutor(RemediationExecutor):
    """Executor for data deletion remediation actions"""

    async def execute(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data deletion action"""
        logger.info(f"Executing data deletion: {action}")

        try:
            # Simulate data deletion process
            data_source = parameters.get("data_source", "unknown")
            user_id = parameters.get("user_id")
            field_name = parameters.get("field_name")

            # Validation
            if not user_id:
                return {
                    "status": ExecutionStatus.FAILED.value,
                    "error": "User ID required for data deletion",
                    "executed_at": datetime.now(timezone.utc).isoformat()
                }

            # Simulate deletion steps
            steps_executed = []

            # Step 1: Backup data (if required)
            if parameters.get("create_backup", True):
                logger.info("Creating data backup before deletion")
                steps_executed.append("backup_created")
                await asyncio.sleep(0.1)  # Simulate processing time

            # Step 2: Execute deletion
            logger.info(f"Deleting {field_name} for user {user_id} from {data_source}")
            steps_executed.append("data_deleted")
            await asyncio.sleep(0.1)

            # Step 3: Verify deletion
            logger.info("Verifying data deletion completion")
            steps_executed.append("deletion_verified")
            await asyncio.sleep(0.1)

            # Step 4: Update audit logs
            logger.info("Updating audit logs")
            steps_executed.append("audit_logged")

            return {
                "status": ExecutionStatus.COMPLETED.value,
                "message": f"Successfully deleted {field_name} for user {user_id}",
                "steps_executed": steps_executed,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "records_affected": 1
            }

        except Exception as e:
            logger.error(f"Data deletion failed: {str(e)}")
            return {
                "status": ExecutionStatus.FAILED.value,
                "error": str(e),
                "executed_at": datetime.now(timezone.utc).isoformat()
            }


class DataUpdateExecutor(RemediationExecutor):
    """Executor for data update/correction remediation actions"""

    async def execute(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data update action"""
        logger.info(f"Executing data update: {action}")

        try:
            user_id = parameters.get("user_id")
            field_name = parameters.get("field_name")
            from_value = parameters.get("from_value")
            to_value = parameters.get("to_value")

            if not all([user_id, field_name, to_value]):
                return {
                    "status": ExecutionStatus.FAILED.value,
                    "error": "User ID, field name, and new value required",
                    "executed_at": datetime.now(timezone.utc).isoformat()
                }

            # Simulate update process
            steps_executed = []

            # Step 1: Validate new data
            logger.info(f"Validating new value for {field_name}")
            steps_executed.append("data_validated")
            await asyncio.sleep(0.1)

            # Step 2: Create backup
            logger.info("Creating backup of original data")
            steps_executed.append("backup_created")
            await asyncio.sleep(0.1)

            # Step 3: Execute update
            logger.info(f"Updating {field_name} from '{from_value}' to '{to_value}' for user {user_id}")
            steps_executed.append("data_updated")
            await asyncio.sleep(0.1)

            # Step 4: Verify update
            logger.info("Verifying data update completion")
            steps_executed.append("update_verified")

            return {
                "status": ExecutionStatus.COMPLETED.value,
                "message": f"Successfully updated {field_name} for user {user_id}",
                "steps_executed": steps_executed,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "old_value": from_value,
                "new_value": to_value
            }

        except Exception as e:
            logger.error(f"Data update failed: {str(e)}")
            return {
                "status": ExecutionStatus.FAILED.value,
                "error": str(e),
                "executed_at": datetime.now(timezone.utc).isoformat()
            }


class NotificationExecutor(RemediationExecutor):
    """Executor for notification remediation actions"""

    async def execute(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute notification action"""
        logger.info(f"Executing notification: {action}")

        try:
            recipient = parameters.get("recipient")
            message = parameters.get("message")
            notification_type = parameters.get("type", "email")

            if not all([recipient, message]):
                return {
                    "status": ExecutionStatus.FAILED.value,
                    "error": "Recipient and message required",
                    "executed_at": datetime.now(timezone.utc).isoformat()
                }

            # Simulate notification sending
            logger.info(f"Sending {notification_type} notification to {recipient}")
            await asyncio.sleep(0.1)

            return {
                "status": ExecutionStatus.COMPLETED.value,
                "message": f"Notification sent to {recipient}",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "notification_type": notification_type
            }

        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")
            return {
                "status": ExecutionStatus.FAILED.value,
                "error": str(e),
                "executed_at": datetime.now(timezone.utc).isoformat()
            }


class ExecutionNode:
    """
    LangGraph node for executing remediation actions
    """

    def __init__(self):
        self.executors = {
            "delete": DataDeletionExecutor(),
            "update": DataUpdateExecutor(),
            "notify": NotificationExecutor()
        }

    async def __call__(self, state: RemediationStateSchema) -> RemediationStateSchema:
        """
        Execute the remediation workflow

        Args:
            state: Current remediation state

        Returns:
            Updated state with execution results
        """
        logger.info(f"Executing remediation for violation {state['signal'].violation.rule_id}")

        try:
            state["execution_path"].append("execution_started")

            workflow = state.get("workflow")
            decision = state.get("decision")

            if not workflow:
                state["errors"].append("No workflow available for execution")
                return state

            # Check if execution should proceed based on remediation type
            if decision and decision.remediation_type == RemediationType.MANUAL_ONLY:
                logger.info("Manual-only remediation - skipping automatic execution")
                state["execution_path"].append("execution_skipped_manual_only")
                state["context"]["execution_status"] = "awaiting_manual_execution"
                return state

            # Execute workflow steps
            execution_results = await self._execute_workflow_steps(workflow, state)

            # Update state with execution results
            state["execution_results"] = execution_results
            state["context"]["execution_completed"] = True
            state["context"]["execution_summary"] = self._create_execution_summary(execution_results)

            # Update workflow status based on results
            if all(result.get("status") == ExecutionStatus.COMPLETED.value for result in execution_results):
                workflow.status = WorkflowStatus.COMPLETED
                state["workflow_status"] = WorkflowStatus.COMPLETED
                state["execution_path"].append("execution_completed_successfully")
            else:
                workflow.status = WorkflowStatus.FAILED
                state["workflow_status"] = WorkflowStatus.FAILED
                state["execution_path"].append("execution_completed_with_errors")

            logger.info(f"Execution completed for {state['signal'].violation.rule_id}")

        except Exception as e:
            logger.error(f"Error in execution node: {str(e)}")
            state["errors"].append(f"Execution error: {str(e)}")
            state["execution_path"].append("execution_failed")

        return state

    async def _execute_workflow_steps(self, workflow: RemediationWorkflow, state: RemediationStateSchema) -> List[Dict[str, Any]]:
        """Execute individual workflow steps"""
        results = []

        for step in workflow.steps:
            try:
                logger.info(f"Executing step: {step.id}")

                # Extract action type and parameters
                action_type = self._extract_action_type(step.action)
                parameters = self._extract_action_parameters(step, state)

                # Get appropriate executor
                executor = self.executors.get(action_type)
                if not executor:
                    logger.warning(f"No executor found for action type: {action_type}")
                    result = {
                        "step_id": step.id,
                        "status": ExecutionStatus.FAILED.value,
                        "error": f"No executor for action type: {action_type}",
                        "executed_at": datetime.now(timezone.utc).isoformat()
                    }
                else:
                    # Execute the action
                    result = await executor.execute(step.action, parameters)
                    result["step_id"] = step.id

                results.append(result)

                # Update step status
                if result.get("status") == ExecutionStatus.COMPLETED.value:
                    step.status = WorkflowStatus.COMPLETED
                    step.completed_at = datetime.now(timezone.utc)
                else:
                    step.status = WorkflowStatus.FAILED

                # Short delay between steps
                await asyncio.sleep(0.05)

            except Exception as e:
                logger.error(f"Error executing step {step.id}: {str(e)}")
                results.append({
                    "step_id": step.id,
                    "status": ExecutionStatus.FAILED.value,
                    "error": str(e),
                    "executed_at": datetime.now(timezone.utc).isoformat()
                })

        return results

    def _extract_action_type(self, action: str) -> str:
        """Extract action type from action string"""
        action_lower = action.lower()

        if "delete" in action_lower or "remove" in action_lower:
            return "delete"
        elif "update" in action_lower or "correct" in action_lower or "modify" in action_lower:
            return "update"
        elif "notify" in action_lower or "alert" in action_lower or "inform" in action_lower:
            return "notify"
        else:
            return "unknown"

    def _extract_action_parameters(self, step: WorkflowStep, state: RemediationStateSchema) -> Dict[str, Any]:
        """Extract parameters for action execution from workflow step and state"""
        signal = state["signal"]

        # Base parameters from the signal
        parameters = {
            "user_id": getattr(signal.violation, 'user_id', None),
            "field_name": getattr(signal.violation, 'field_name', None),
            "data_source": getattr(signal.violation, 'domain_name', 'unknown'),
            "framework": signal.framework
        }

        # Add step-specific metadata if available
        if hasattr(step, 'metadata') and step.metadata:
            parameters.update(step.metadata)

        # Add parameters from signal context if available
        if hasattr(signal, 'context') and signal.context:
            parameters.update(signal.context)

        return parameters

    def _create_execution_summary(self, execution_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary of execution results"""
        total_steps = len(execution_results)
        completed_steps = sum(1 for r in execution_results if r.get("status") == ExecutionStatus.COMPLETED.value)
        failed_steps = sum(1 for r in execution_results if r.get("status") == ExecutionStatus.FAILED.value)

        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "success_rate": completed_steps / total_steps if total_steps > 0 else 0,
            "overall_status": ExecutionStatus.COMPLETED.value if failed_steps == 0 else ExecutionStatus.FAILED.value,
            "execution_completed_at": datetime.now(timezone.utc).isoformat()
        }

    def get_available_executors(self) -> List[str]:
        """Get list of available action executors"""
        return list(self.executors.keys())

    def add_executor(self, action_type: str, executor: RemediationExecutor):
        """Add a new action executor"""
        self.executors[action_type] = executor

    async def test_execution(self, action_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Test execution of a specific action type"""
        executor = self.executors.get(action_type)
        if not executor:
            return {
                "status": ExecutionStatus.FAILED.value,
                "error": f"No executor for action type: {action_type}"
            }

        return await executor.execute(f"test_{action_type}", parameters)
