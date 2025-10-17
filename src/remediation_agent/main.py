"""
Main Remediation Agent

This module provides the main entry point for the AI-powered remediation agent
that processes compliance violations and orchestrates intelligent remediation workflows.
"""

import asyncio
import logging
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .graphs.remediation_graph import RemediationGraph
from .state.models import (
    RemediationSignal,
    RemediationMetrics,
    RemediationType,
    WorkflowStatus,
    UrgencyLevel
)
from .tools.notification_tool import NotificationTool
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation,
    DataProcessingActivity,
    RiskLevel
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RemediationAgent:
    """
    Main AI-powered remediation agent that receives compliance signals
    and orchestrates intelligent remediation workflows.
    """

    def __init__(self):
        """Initialize the remediation agent"""
        self.graph = RemediationGraph()
        self.notification_tool = NotificationTool()
        self.metrics = RemediationMetrics()

        # Agent configuration
        self.config = {
            "max_concurrent_workflows": 10,
            "default_timeout_hours": 72,
            "enable_notifications": True,
            "auto_retry_failed_workflows": True,
            "max_retry_attempts": 3
        }

        logger.info("Remediation Agent initialized")

    async def process_compliance_violation(
        self,
        violation: ComplianceViolation,
        activity: DataProcessingActivity,
        framework: str,
        urgency: Optional[RiskLevel] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a compliance violation and initiate remediation workflow

        Args:
            violation: The compliance violation to remediate
            activity: Associated data processing activity
            framework: Compliance framework (e.g., 'gdpr_eu', 'pdpa_singapore')
            urgency: Override urgency level (defaults to violation risk level)
            context: Additional context for processing

        Returns:
            Dictionary containing processing results and workflow information
        """
        logger.info(f"🔄 [AGENT-PROCESS-START] Processing compliance violation {violation.rule_id}")
        logger.info(f"📊 [VIOLATION-DETAILS] Risk: {violation.risk_level.value}, Framework: {framework}")
        logger.info(f"🎯 [ACTIVITY-INFO] Activity: {activity.id}, Data types: {[dt.value for dt in activity.data_types]}")

        try:
            # Create remediation signal
            logger.info(f"📡 [SIGNAL-CREATE] Creating remediation signal for {violation.rule_id}")
            signal = self._create_remediation_signal(
                violation, activity, framework, urgency, context
            )
            logger.info(f"✅ [SIGNAL-CREATED] Signal for violation: {signal.violation.rule_id}, Priority: {signal.urgency.value}")
            logger.info(f"🔧 [SIGNAL-CONTEXT] Context keys: {list(signal.context.keys()) if signal.context else 'None'}")

            # Process through the remediation graph
            logger.info(f"🚀 [LANGGRAPH-START] Starting LangGraph workflow processing for {violation.rule_id}")
            result = await self.graph.process_remediation_signal(signal)
            logger.info(f"✅ [LANGGRAPH-COMPLETE] LangGraph workflow completed for {violation.rule_id}")
            logger.info(f"📊 [WORKFLOW-RESULT] Success: {result.get('success')}, Keys: {list(result.keys())}")

            # Update metrics
            logger.info(f"📈 [METRICS-UPDATE] Updating agent metrics for {violation.rule_id}")
            await self._update_metrics(result)
            logger.info(f"✅ [METRICS-UPDATED] Metrics successfully updated")

            # Send completion notification if enabled
            if self.config.get("enable_notifications", True):
                logger.info(f"📧 [NOTIFICATION-SEND] Sending completion notification for {violation.rule_id}")
                await self._send_completion_notification(result)
                logger.info(f"✅ [NOTIFICATION-SENT] Completion notification sent")
            else:
                logger.info(f"🔕 [NOTIFICATION-DISABLED] Notifications disabled, skipping for {violation.rule_id}")

            success_status = 'Success' if result.get('success') else 'Failed'
            logger.info(f"🎉 [AGENT-PROCESS-COMPLETE] Violation {violation.rule_id} processing complete: {success_status}")
            decision_summary = result.get("decision_info")
            if decision_summary:
                logger.info(
                    "🧾 [REMEDIATION-DECISION-SUMMARY] %s",
                    json.dumps(decision_summary, default=str)
                )

            return result

        except Exception as e:
            logger.error(f"💥 [AGENT-PROCESS-ERROR] Error processing violation {violation.rule_id}: {str(e)}")
            logger.error(f"📊 [ERROR-TYPE] Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"🔍 [ERROR-STACK] {traceback.format_exc()}")

            error_result = {
                "success": False,
                "error": str(e),
                "violation_id": violation.rule_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            logger.info(f"📤 [ERROR-RESPONSE] Returning error response for {violation.rule_id}")
            return error_result

    def _create_remediation_signal(
        self,
        violation: ComplianceViolation,
        activity: DataProcessingActivity,
        framework: str,
        urgency: Optional[RiskLevel],
        context: Optional[Dict[str, Any]]
    ) -> RemediationSignal:
        """Create a remediation signal from the input parameters"""

        # Normalise inputs in case downstream callers provide dictionaries
        try:
            if not isinstance(violation, ComplianceViolation):
                if isinstance(violation, BaseModel):
                    violation = ComplianceViolation.model_validate(violation.model_dump())
                else:
                    violation = ComplianceViolation.model_validate(violation)
        except Exception as exc:  # pragma: no cover - log and fallback to placeholder
            logger.warning(
                "Failed to validate violation payload (%s) – using placeholder violation",
                exc,
            )
            violation = ComplianceViolation(
                rule_id=f"fallback_{uuid.uuid4().hex[:8]}",
                description="Fallback violation due to validation error",
                risk_level=RiskLevel.MEDIUM,
                remediation_actions=[],
            )

        try:
            if not isinstance(activity, DataProcessingActivity):
                if isinstance(activity, BaseModel):
                    activity = DataProcessingActivity.model_validate(activity.model_dump())
                else:
                    activity = DataProcessingActivity.model_validate(activity)
        except Exception as exc:  # pragma: no cover - log and fallback to placeholder
            logger.warning(
                "Failed to validate activity payload (%s) – using placeholder activity",
                exc,
            )
            activity = DataProcessingActivity(
                id=f"fallback_activity_{uuid.uuid4().hex[:8]}",
                name="Fallback Activity",
                purpose="unspecified",
                data_types=[],
            )

        # Determine urgency level
        if urgency is None and violation is not None:
            urgency = violation.risk_level
        urgency_value = getattr(urgency, "value", urgency)
        try:
            urgency_level = UrgencyLevel(str(urgency_value).lower())
        except Exception:
            urgency_level = UrgencyLevel.MEDIUM

        return RemediationSignal(
            violation=violation,
            activity=activity,
            framework=framework,
            urgency_level=urgency_level,
            priority=urgency_level.value,
            context=context or {},
            received_at=datetime.now(timezone.utc)
        )

    async def get_workflow_status(self, violation_id: str) -> Dict[str, Any]:
        """
        Get the status of a remediation workflow

        Args:
            violation_id: ID of the violation/workflow to check

        Returns:
            Workflow status information
        """
        try:
            return await self.graph.get_workflow_status(violation_id)
        except Exception as e:
            logger.error(f"Error getting workflow status for {violation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "violation_id": violation_id
            }

    async def resume_workflow(self, violation_id: str) -> Dict[str, Any]:
        """
        Resume a paused or interrupted workflow

        Args:
            violation_id: ID of the violation/workflow to resume

        Returns:
            Resume operation result
        """
        try:
            return await self.graph.resume_workflow(violation_id)
        except Exception as e:
            logger.error(f"Error resuming workflow for {violation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "violation_id": violation_id
            }

    async def process_multiple_violations(
        self,
        violations_data: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process multiple compliance violations concurrently

        Args:
            violations_data: List of violation data dictionaries
            max_concurrent: Maximum concurrent processing (defaults to config)

        Returns:
            Results summary for all processed violations
        """
        max_concurrent = max_concurrent or self.config.get("max_concurrent_workflows", 10)

        logger.info(f"Processing {len(violations_data)} violations with max concurrency {max_concurrent}")

        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []

        async def process_single_violation(violation_data: Dict[str, Any]):
            async with semaphore:
                try:
                    return await self.process_compliance_violation(**violation_data)
                except Exception as e:
                    logger.error(f"Error in concurrent processing: {str(e)}")
                    return {
                        "success": False,
                        "error": str(e),
                        "violation_id": violation_data.get("violation", {}).get("rule_id", "unknown")
                    }

        # Create tasks for all violations
        for violation_data in violations_data:
            task = asyncio.create_task(process_single_violation(violation_data))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Compile summary
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
        failed = len(results) - successful

        summary = {
            "total_processed": len(violations_data),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(violations_data) if violations_data else 0,
            "results": results,
            "processing_timestamp": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Batch processing complete: {successful}/{len(violations_data)} successful")

        return summary

    async def get_agent_metrics(self) -> RemediationMetrics:
        """Get current agent metrics"""
        # Update metrics from graph state manager
        graph_metrics = self.graph.state_manager.get_metrics()

        # Merge with agent metrics
        self.metrics.total_violations_processed = graph_metrics.total_violations_processed
        self.metrics.automatic_remediations = graph_metrics.automatic_remediations
        self.metrics.human_loop_remediations = graph_metrics.human_loop_remediations
        self.metrics.manual_remediations = graph_metrics.manual_remediations
        self.metrics.success_rate = graph_metrics.success_rate

        return self.metrics

    async def get_active_workflows(self) -> Dict[str, Any]:
        """Get information about currently active workflows"""

        active_workflows = self.graph.state_manager.active_workflows

        workflow_summaries = []
        for workflow_id, workflow in active_workflows.items():
            summary = {
                "workflow_id": workflow_id,
                "violation_id": workflow.violation_id,
                "status": workflow.status.value,
                "remediation_type": workflow.remediation_type.value,
                "priority": workflow.priority.value,
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
                "steps_total": len(workflow.steps),
                "steps_completed": len([s for s in workflow.steps if s.status == WorkflowStatus.COMPLETED])
            }
            workflow_summaries.append(summary)

        return {
            "active_workflow_count": len(active_workflows),
            "workflows": workflow_summaries,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def emergency_stop_workflow(self, violation_id: str, reason: str) -> Dict[str, Any]:
        """
        Emergency stop for a workflow

        Args:
            violation_id: ID of the workflow to stop
            reason: Reason for emergency stop

        Returns:
            Stop operation result
        """
        logger.warning(f"Emergency stop requested for workflow {violation_id}: {reason}")

        try:
            # Find and stop the workflow
            workflow = self.graph.state_manager.active_workflows.get(violation_id)

            if not workflow:
                return {
                    "success": False,
                    "error": "Workflow not found or already completed",
                    "violation_id": violation_id
                }

            # Update workflow status
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.metadata["emergency_stop_reason"] = reason

            # Move to completed workflows
            self.graph.state_manager._move_to_completed(workflow)

            # Send emergency notification
            if self.config.get("enable_notifications", True):
                await self.notification_tool.send_urgent_alert(
                    workflow,
                    f"Workflow emergency stop: {reason}",
                    ["Review stopped workflow", "Assess impact", "Plan alternative actions"]
                )

            logger.info(f"Workflow {violation_id} stopped successfully")

            return {
                "success": True,
                "violation_id": violation_id,
                "stopped_at": workflow.completed_at.isoformat(),
                "reason": reason
            }

        except Exception as e:
            logger.error(f"Error stopping workflow {violation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "violation_id": violation_id
            }

    async def _update_metrics(self, processing_result: Dict[str, Any]):
        """Update agent metrics based on processing result"""

        self.metrics.total_violations_processed += 1

        if processing_result.get("success", False):
            decision_info = processing_result.get("decision_info", {})
            remediation_type = decision_info.get("remediation_type")

            if remediation_type == "automatic":
                self.metrics.automatic_remediations += 1
            elif remediation_type == "human_in_loop":
                self.metrics.human_loop_remediations += 1
            elif remediation_type == "manual_only":
                self.metrics.manual_remediations += 1

            # Update framework metrics
            framework = processing_result.get("signal_info", {}).get("framework")
            if framework:
                if framework not in self.metrics.by_framework:
                    self.metrics.by_framework[framework] = 0
                self.metrics.by_framework[framework] += 1

        # Recalculate success rate
        total = self.metrics.total_violations_processed
        successful = (self.metrics.automatic_remediations +
                     self.metrics.human_loop_remediations +
                     self.metrics.manual_remediations)

        if total > 0:
            self.metrics.success_rate = successful / total

    async def _send_completion_notification(self, processing_result: Dict[str, Any]):
        """Send completion notification for processing result"""

        try:
            workflow_info = processing_result.get("workflow_info", {})
            if not workflow_info:
                return

            # Create a basic workflow object for notification
            from .state.models import RemediationWorkflow, WorkflowType
            workflow = RemediationWorkflow(
                id=workflow_info.get("workflow_id", "unknown"),
                violation_id=workflow_info.get("violation_id", "unknown"),
                activity_id=workflow_info.get("activity_id", "unknown"),
                remediation_type=RemediationType.HUMAN_IN_LOOP,  # Default
                workflow_type=WorkflowType.HUMAN_IN_LOOP,  # Default
                metadata={"completion_result": processing_result}
            )

            # Import NotificationType separately
            from .tools.notification_tool import NotificationType

            if processing_result.get("success", False):
                # Calculate workflow duration
                duration = "N/A"
                if workflow.created_at and workflow.completed_at:
                    duration_delta = workflow.completed_at - workflow.created_at
                    duration_minutes = int(duration_delta.total_seconds() / 60)
                    if duration_minutes < 60:
                        duration = f"{duration_minutes} minutes"
                    else:
                        duration_hours = duration_minutes / 60
                        duration = f"{duration_hours:.1f} hours"
                elif workflow.created_at:
                    # If no completed_at, calculate from created_at to now
                    duration_delta = datetime.now(timezone.utc) - workflow.created_at
                    duration_minutes = int(duration_delta.total_seconds() / 60)
                    if duration_minutes < 60:
                        duration = f"{duration_minutes} minutes (ongoing)"
                    else:
                        duration_hours = duration_minutes / 60
                        duration = f"{duration_hours:.1f} hours (ongoing)"

                await self.notification_tool.send_workflow_notification(
                    NotificationType.WORKFLOW_COMPLETED,
                    workflow,
                    {
                        "completion_summary": "Remediation workflow completed successfully",
                        "duration": duration,
                        "final_status": "Completed successfully"
                    }
                )
            else:
                # Prepare failed workflow notification data
                failed_at = datetime.now(timezone.utc).isoformat()
                next_steps_list = processing_result.get("next_steps", [
                    "Review error details",
                    "Check system logs",
                    "Contact support if needed",
                    "Retry manual remediation if appropriate"
                ])
                next_steps_formatted = "\n".join(f"• {step}" for step in next_steps_list)

                await self.notification_tool.send_workflow_notification(
                    NotificationType.WORKFLOW_FAILED,
                    workflow,
                    {
                        "error_message": processing_result.get("error", "Unknown error"),
                        "next_steps": next_steps_formatted,
                        "failed_at": failed_at
                    }
                )

        except Exception as e:
            logger.warning(f"Could not send completion notification: {str(e)}")

    def print_graph_structure(self):
        """Print the ASCII representation of the LangGraph structure"""
        return self.graph.print_graph_ascii()

    def get_graph_ascii(self) -> str:
        """Get the ASCII representation of the graph"""
        return self.graph.get_graph_ascii()

    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the agent configuration and capabilities"""

        return {
            "agent_version": "1.0.0",
            "capabilities": [
                "Intelligent violation analysis",
                "Automated remediation decision-making",
                "Human-in-the-loop workflow orchestration",
                "AWS SQS integration for workflow management",
                "Multi-framework compliance support",
                "Real-time notification system",
                "Concurrent violation processing"
            ],
            "supported_frameworks": [
                "gdpr_eu",
                "pdpa_singapore",
                "ccpa_california",
                "pipeda_canada",
                "lgpd_brazil"
            ],
            "configuration": self.config,
            "graph_visualization": self.graph.get_graph_visualization(),
            "agent_metrics": self.metrics.dict() if hasattr(self.metrics, 'dict') else str(self.metrics)
        }


# Convenience function for direct usage
async def remediate_compliance_violation(
    violation: ComplianceViolation,
    activity: DataProcessingActivity,
    framework: str,
    urgency: Optional[RiskLevel] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to directly remediate a compliance violation

    Args:
        violation: The compliance violation to remediate
        activity: Associated data processing activity
        framework: Compliance framework
        urgency: Override urgency level
        context: Additional context

    Returns:
        Processing result
    """
    agent = RemediationAgent()
    return await agent.process_compliance_violation(
        violation, activity, framework, urgency, context
    )
