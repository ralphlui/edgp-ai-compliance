"""
Workflow Node for LangGraph remediation workflow

This node creates and manages remediation workflows, including
SQS queue setup and step orchestration.
"""

import logging
import json
from typing import Dict, Any, Optional

from ...agents.workflow_agent import WorkflowAgent
from ...tools.sqs_tool import SQSTool
from ...state.remediation_state import RemediationState
from ...state.models import WorkflowStatus, RemediationType

logger = logging.getLogger(__name__)


class WorkflowNode:
    """
    LangGraph node for creating and managing remediation workflows
    """

    def __init__(self) -> None:
        self.workflow_agent = WorkflowAgent()
        self.sqs_tool = SQSTool()

    async def __call__(self, state: RemediationState) -> RemediationState:
        """
        Execute the workflow node

        Args:
            state: Current remediation state

        Returns:
            Updated state with workflow and SQS queue setup
        """
        violation_id = state['signal'].violation.rule_id
        logger.info(f"🏗️ [WORKFLOW-START] Executing workflow node for violation {violation_id}")

        try:
            def _safe_float(value: Any, default: float = 0.0) -> float:
                try:
                    if value is None:
                        return default
                    return float(value)
                except (TypeError, ValueError):
                    return default

            # Add to execution path
            logger.info(f"📝 [EXECUTION-PATH] Adding 'workflow_creation_started' to execution path")
            state["execution_path"].append("workflow_creation_started")

            # Get decision and analysis results
            logger.info(f"📊 [DECISION-CHECK] Retrieving decision for workflow creation")
            decision = state.get("decision")
            if not decision:
                logger.error(f"❌ [DECISION-MISSING] No decision available for workflow creation")
                raise ValueError("No decision available for workflow creation")

            logger.info(f"✅ [DECISION-FOUND] Decision type: {decision.remediation_type.value}")
            decision_confidence = _safe_float(getattr(decision, "confidence_score", None), 0.0)
            logger.info("📈 [DECISION-CONFIDENCE] Confidence: %.2f", decision_confidence)

            complexity_assessment = state.get("complexity_assessment") or {}
            feasibility_score = _safe_float(state.get("feasibility_score"), 0.0)
            feasibility_details = {
                "feasibility_score": feasibility_score,
                "complexity_assessment": complexity_assessment
            }
            logger.info(
                "📊 [FEASIBILITY-DATA] Score: %.2f, Complexity factors: %d",
                feasibility_score,
                len(complexity_assessment) if isinstance(complexity_assessment, dict) else 0,
            )

            prompts = state.setdefault("context", {}).setdefault("node_prompts", {})
            workflow_prompt = {
                "violation_id": state["signal"].violation.rule_id,
                "decision": {
                    "remediation_type": decision.remediation_type.value,
                    "confidence_score": decision_confidence,
                    "estimated_effort": getattr(decision, "estimated_effort", None),
                    "risk_if_delayed": getattr(decision, "risk_if_delayed", None).value
                    if hasattr(getattr(decision, "risk_if_delayed", None), "value")
                    else getattr(decision, "risk_if_delayed", None),
                },
                "feasibility_score": feasibility_score,
                "complexity": complexity_assessment.get("overall_complexity"),
                "queue_config": {
                    "main_queue_url": self.sqs_tool.config.get("main_queue_url"),
                    "dlq_url": self.sqs_tool.config.get("dlq_url"),
                }
            }
            logger.info(
                "🧾 [NODE-PROMPT][workflow] %s",
                json.dumps(workflow_prompt, default=str)
            )
            prompts["workflow"] = workflow_prompt

            # Create the workflow
            logger.info(f"🔧 [WORKFLOW-CREATE] Creating workflow via WorkflowAgent for {violation_id}")
            workflow = await self.workflow_agent.create_workflow(
                state["signal"], decision, feasibility_details
            )
            logger.info(f"✅ [WORKFLOW-CREATED] Workflow ID: {workflow.id}")
            logger.info(f"🔗 [WORKFLOW-DETAILS] Steps: {len(workflow.steps)}, Type: {workflow.workflow_type.value}")

            state["workflow"] = workflow
            state["workflow_status"] = WorkflowStatus.PENDING
            logger.info(f"📝 [STATE-UPDATE] Workflow stored in state with PENDING status")

            # Use existing SQS main queue from configuration
            logger.info(f"📡 [SQS-CONFIGURE] Configuring existing SQS main queue for workflow {workflow.id}")
            queue_url = self._get_main_queue_url()

            if queue_url:
                logger.info(f"✅ [SQS-CONFIGURED] Using existing main queue")
                logger.info(f"🔗 [SQS-QUEUE-URL] {queue_url}")

                state["sqs_queue_created"] = True
                state["sqs_queue_url"] = queue_url
                workflow.sqs_queue_url = queue_url
                logger.info(f"📝 [STATE-UPDATE] SQS queue info stored in state and workflow")
            else:
                logger.warning(f"⚠️ [SQS-NO-CONFIG] No SQS main queue URL configured")
                queue_name = f"remediation-workflow-{workflow.id}"
                logger.info(f"🛠️ [SQS-FALLBACK] Attempting to create workflow-specific queue {queue_name}")
                queue_result = await self.sqs_tool.create_remediation_queue(queue_name, workflow.id)

                if queue_result.get("success"):
                    queue_url = queue_result.get("queue_url")
                    state["sqs_queue_created"] = True
                    state["sqs_queue_url"] = queue_url
                    workflow.sqs_queue_url = queue_url
                    logger.info(f"✅ [SQS-FALLBACK-SUCCESS] Created fallback queue {queue_url}")
                else:
                    error_msg = queue_result.get("error", "Unknown error")
                    state["errors"].append("No SQS main queue URL configured in settings")
                    state["errors"].append(f"Failed to create fallback queue: {error_msg}")
                    logger.error(f"❌ [SQS-FALLBACK-FAILED] {error_msg}")

            # Initialize workflow based on remediation type
            await self._initialize_workflow_execution(state)

            # Update context
            state["context"].update({
                "workflow_created": True,
                "workflow_id": workflow.id,
                "total_steps": len(workflow.steps),
                "sqs_queue_available": state.get("sqs_queue_created", False)
            })

            state["execution_path"].append("workflow_creation_completed")

            logger.info(f"Workflow created with {len(workflow.steps)} steps: {workflow.id}")

            return state

        except Exception as e:
            logger.error(f"Error in workflow node: {str(e)}")
            state["errors"].append(f"Workflow creation error: {str(e)}")
            state["execution_path"].append("workflow_creation_failed")
            return state

    def _get_main_queue_url(self) -> Optional[str]:
        """Get the main SQS queue URL from configuration"""
        try:
            # Import settings to get the main queue URL
            from config.settings import settings
            queue_url = settings.sqs_main_queue_url
            logger.info(f"📋 [SQS-CONFIG] Retrieved main queue URL from settings")
            return queue_url
        except ImportError:
            # Fallback to environment variable
            import os
            queue_url = os.getenv("SQS_MAIN_QUEUE_URL")
            logger.info(f"📋 [SQS-ENV] Retrieved main queue URL from environment")
            return queue_url
        except Exception as e:
            logger.error(f"❌ [SQS-CONFIG-ERROR] Failed to get main queue URL: {str(e)}")
            return None

    async def _initialize_workflow_execution(self, state: RemediationState):
        """Initialize workflow execution based on remediation type"""

        workflow = state["workflow"]
        decision = state["decision"]

        if decision.remediation_type == RemediationType.AUTOMATIC:
            await self._initialize_automatic_workflow(state)
        elif decision.remediation_type == RemediationType.HUMAN_IN_LOOP:
            await self._initialize_human_loop_workflow(state)
        else:  # MANUAL_ONLY
            await self._initialize_manual_workflow(state)

    async def _initialize_automatic_workflow(self, state: RemediationState):
        """Initialize automatic workflow execution"""

        workflow = state["workflow"]
        queue_url = state.get("sqs_queue_url")

        # Start workflow
        workflow.status = WorkflowStatus.IN_PROGRESS
        workflow.started_at = workflow.created_at

        # Send initial message to SQS queue to start processing
        if queue_url:
            initial_message = {
                "type": "workflow_start",
                "workflow_id": workflow.id,
                "remediation_type": "automatic",
                "next_step": workflow.steps[0].id if workflow.steps else None,
                "signal": {
                    "violation_id": state["signal"].violation.rule_id,
                    "urgency": state["signal"].urgency.value
                }
            }

            await self.sqs_tool.send_workflow_message(queue_url, initial_message)

        logger.info(f"Automatic workflow {workflow.id} initialized and started")

    async def _initialize_human_loop_workflow(self, state: RemediationState):
        """Initialize human-in-loop workflow"""

        workflow = state["workflow"]
        state["requires_human"] = True

        # Set workflow to pending human input
        workflow.status = WorkflowStatus.REQUIRES_HUMAN

        # Create initial human task
        human_task_context = {
            "workflow_id": workflow.id,
            "decision_confidence": state["decision"].confidence_score,
            "estimated_effort": state["decision"].estimated_effort,
            "prerequisites": state["decision"].prerequisites
        }

        state["context"]["human_task_required"] = True
        state["context"]["human_task_context"] = human_task_context

        logger.info(f"Human-in-loop workflow {workflow.id} initialized - awaiting human input")

    async def _initialize_manual_workflow(self, state: RemediationState):
        """Initialize manual-only workflow"""

        workflow = state["workflow"]
        state["requires_human"] = True

        # Set workflow to pending manual execution
        workflow.status = WorkflowStatus.REQUIRES_HUMAN

        # Create urgent human task
        urgent_task_context = {
            "workflow_id": workflow.id,
            "urgency": "high",
            "manual_only": True,
            "estimated_effort": state["decision"].estimated_effort,
            "risk_if_delayed": state["decision"].risk_if_delayed.value
        }

        state["context"]["urgent_human_task_required"] = True
        state["context"]["urgent_task_context"] = urgent_task_context

        logger.info(f"Manual workflow {workflow.id} initialized - requires immediate human attention")

    async def execute_next_workflow_step(self, state: RemediationState) -> Dict[str, Any]:
        """Execute the next step in the workflow"""

        workflow = state["workflow"]
        if not workflow or not workflow.steps:
            return {"success": False, "error": "No workflow or steps available"}

        # Find next pending step
        next_step = None
        for step in workflow.steps:
            if step.status == WorkflowStatus.PENDING:
                next_step = step
                break

        if not next_step:
            return {"success": False, "error": "No pending steps found"}

        # Execute the step
        try:
            step_result = await self.workflow_agent.execute_workflow_step(workflow, next_step.id)

            # Update state based on result
            if step_result.get("success"):
                state["execution_path"].append(f"step_completed_{next_step.id}")

                # Check if workflow is complete
                if self._is_workflow_complete(workflow):
                    workflow.status = WorkflowStatus.COMPLETED
                    state["workflow_status"] = WorkflowStatus.COMPLETED
                    state["execution_path"].append("workflow_completed")

            else:
                state["errors"].append(f"Step {next_step.id} failed: {step_result.get('error')}")

            return step_result

        except Exception as e:
            logger.error(f"Error executing workflow step: {str(e)}")
            return {"success": False, "error": str(e)}

    def _is_workflow_complete(self, workflow) -> bool:
        """Check if all workflow steps are completed"""

        if not workflow.steps:
            return True

        completed_steps = [s for s in workflow.steps if s.status == WorkflowStatus.COMPLETED]
        failed_steps = [s for s in workflow.steps if s.status == WorkflowStatus.FAILED]

        # Workflow is complete if all steps are either completed or failed with no retries
        all_steps_processed = len(completed_steps) + len(failed_steps) == len(workflow.steps)

        return all_steps_processed

    async def monitor_workflow_progress(self, state: RemediationState) -> Dict[str, Any]:
        """Monitor and report on workflow progress"""

        workflow = state["workflow"]
        if not workflow:
            return {"error": "No workflow to monitor"}

        progress_info = {
            "workflow_id": workflow.id,
            "status": workflow.status.value,
            "total_steps": len(workflow.steps),
            "completed_steps": len([s for s in workflow.steps if s.status == WorkflowStatus.COMPLETED]),
            "failed_steps": len([s for s in workflow.steps if s.status == WorkflowStatus.FAILED]),
            "pending_steps": len([s for s in workflow.steps if s.status == WorkflowStatus.PENDING]),
            "in_progress_steps": len([s for s in workflow.steps if s.status == WorkflowStatus.IN_PROGRESS]),
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "sqs_queue_url": workflow.sqs_queue_url
        }

        # Calculate progress percentage
        if workflow.steps:
            progress_info["progress_percentage"] = (
                progress_info["completed_steps"] / progress_info["total_steps"] * 100
            )
        else:
            progress_info["progress_percentage"] = 0

        # Get queue statistics if available
        if workflow.sqs_queue_url:
            try:
                queue_stats = await self.sqs_tool.get_queue_attributes(workflow.sqs_queue_url)
                if queue_stats.get("success"):
                    progress_info["queue_stats"] = {
                        "messages_available": queue_stats.get("message_count", 0),
                        "messages_in_flight": queue_stats.get("messages_in_flight", 0)
                    }
            except Exception as e:
                logger.warning(f"Could not get queue statistics: {str(e)}")

        return progress_info

    def should_proceed_to_human_loop(self, state: RemediationState) -> bool:
        """Determine if the workflow should proceed to human loop processing"""

        decision = state.get("decision")
        if not decision:
            return True  # Conservative default

        return decision.remediation_type in [
            RemediationType.HUMAN_IN_LOOP,
            RemediationType.MANUAL_ONLY
        ]

    def get_workflow_summary(self, state: RemediationState) -> Dict[str, Any]:
        """Get a summary of the workflow for reporting"""

        workflow = state.get("workflow")
        if not workflow:
            return {"error": "No workflow available"}

        return {
            "workflow_id": workflow.id,
            "violation_id": workflow.violation_id,
            "activity_id": workflow.activity_id,
            "remediation_type": workflow.remediation_type.value,
            "status": workflow.status.value,
            "priority": workflow.priority.value,
            "total_steps": len(workflow.steps),
            "sqs_queue_created": bool(workflow.sqs_queue_url),
            "sqs_queue_url": workflow.sqs_queue_url,
            "metadata": workflow.metadata,
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None
        }
