"""
Notification Tool for remediation workflows

This tool handles notifications for human-in-the-loop workflows,
alerts, and status updates during remediation processes.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from enum import Enum
import asyncio

from ..state.models import (
    RemediationWorkflow,
    HumanTask,
    WorkflowStatus,
    RemediationType,
    RiskLevel
)

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications"""
    WORKFLOW_STARTED = "workflow_started"
    HUMAN_INTERVENTION_REQUIRED = "human_intervention_required"
    APPROVAL_NEEDED = "approval_needed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    URGENT_ATTENTION = "urgent_attention"
    STATUS_UPDATE = "status_update"
    DEADLINE_APPROACHING = "deadline_approaching"


class NotificationPriority(str, Enum):
    """Notification priorities"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(str, Enum):
    """Available notification channels"""
    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationTool:
    """
    Tool for managing notifications in remediation workflows
    """

    def __init__(self):
        # Notification templates
        self.templates = {
            NotificationType.WORKFLOW_STARTED: {
                "subject": "Remediation Workflow Started: {workflow_id}",
                "template": """
A new remediation workflow has been started:

Workflow ID: {workflow_id}
Violation: {violation_description}
Remediation Type: {remediation_type}
Priority: {priority}
Started At: {started_at}

Details: {details_url}
"""
            },
            NotificationType.HUMAN_INTERVENTION_REQUIRED: {
                "subject": "Human Intervention Required: {workflow_id}",
                "template": """
Human intervention is required for a remediation workflow:

Workflow ID: {workflow_id}
Violation: {violation_description}
Task: {task_title}
Assignee: {assignee}
Due Date: {due_date}
Priority: {priority}

Required Actions:
{required_actions}

Please review and take action: {action_url}
"""
            },
            NotificationType.APPROVAL_NEEDED: {
                "subject": "Approval Required: {workflow_id}",
                "template": """
Approval is required to proceed with remediation:

Workflow ID: {workflow_id}
Violation: {violation_description}
Approval Type: {approval_type}
Requested By: {requested_by}
Priority: {priority}

Summary:
{approval_summary}

Approve/Reject: {approval_url}
"""
            },
            NotificationType.WORKFLOW_COMPLETED: {
                "subject": "Remediation Completed: {workflow_id}",
                "template": """
Remediation workflow has been completed successfully:

Workflow ID: {workflow_id}
Violation: {violation_description}
Completion Time: {completed_at}
Duration: {duration}
Final Status: {final_status}

Summary:
{completion_summary}

View Report: {report_url}
"""
            },
            NotificationType.WORKFLOW_FAILED: {
                "subject": "Remediation Failed: {workflow_id}",
                "template": """
Remediation workflow has failed:

Workflow ID: {workflow_id}
Violation: {violation_description}
Failed At: {failed_at}
Error: {error_message}
Priority: {priority}

Next Steps:
{next_steps}

Review Details: {details_url}
"""
            },
            NotificationType.URGENT_ATTENTION: {
                "subject": "URGENT: Immediate Attention Required - {workflow_id}",
                "template": """
🚨 URGENT: Immediate attention required for remediation workflow

Workflow ID: {workflow_id}
Violation: {violation_description}
Issue: {urgent_issue}
Risk Level: {risk_level}
Time Sensitive: {time_constraint}

IMMEDIATE ACTION REQUIRED:
{immediate_actions}

Contact: {emergency_contact}
Escalation: {escalation_procedure}
"""
            }
        }

        # Channel configurations
        self.channel_configs = {
            NotificationChannel.EMAIL: {
                "enabled": True,
                "max_retries": 3,
                "retry_delay": 300  # 5 minutes
            },
            NotificationChannel.SLACK: {
                "enabled": True,
                "max_retries": 2,
                "retry_delay": 60  # 1 minute
            },
            NotificationChannel.SMS: {
                "enabled": False,  # Requires external service
                "max_retries": 2,
                "retry_delay": 30
            },
            NotificationChannel.WEBHOOK: {
                "enabled": True,
                "max_retries": 3,
                "retry_delay": 120
            }
        }

        # Recipient mappings based on roles and priorities
        self.recipient_mappings = {
            RiskLevel.CRITICAL: {
                "roles": ["dpo", "compliance_manager", "security_team"],
                "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.SMS]
            },
            RiskLevel.HIGH: {
                "roles": ["compliance_team", "dpo"],
                "channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK]
            },
            RiskLevel.MEDIUM: {
                "roles": ["compliance_team"],
                "channels": [NotificationChannel.EMAIL]
            },
            RiskLevel.LOW: {
                "roles": ["compliance_team"],
                "channels": [NotificationChannel.IN_APP]
            }
        }

    async def send_workflow_notification(
        self,
        notification_type: NotificationType,
        workflow: RemediationWorkflow,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a notification for a workflow event

        Args:
            notification_type: Type of notification to send
            workflow: The workflow to notify about
            additional_context: Additional context for the notification

        Returns:
            Notification result
        """
        logger.info(f"Sending {notification_type} notification for workflow {workflow.id}")

        try:
            # Determine priority and recipients
            priority = self._determine_priority(notification_type, workflow)
            recipients = self._get_recipients(workflow.priority, notification_type)

            # Prepare notification content
            content = self._prepare_notification_content(
                notification_type, workflow, additional_context or {}
            )

            # Determine channels
            channels = self._determine_channels(priority, workflow.priority)

            # Send notifications
            results = {}
            for channel in channels:
                channel_result = await self._send_via_channel(
                    channel, content, recipients, priority
                )
                results[channel.value] = channel_result

            # Log notification
            await self._log_notification(notification_type, workflow, results)

            overall_success = any(result.get("success", False) for result in results.values())

            return {
                "success": overall_success,
                "notification_type": notification_type,
                "workflow_id": workflow.id,
                "channels_used": list(results.keys()),
                "results": results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "notification_type": notification_type,
                "workflow_id": workflow.id
            }

    async def send_human_task_notification(
        self,
        task: HumanTask,
        workflow: RemediationWorkflow,
        notification_type: NotificationType = NotificationType.HUMAN_INTERVENTION_REQUIRED
    ) -> Dict[str, Any]:
        """
        Send notification for a human task

        Args:
            task: The human task
            workflow: Associated workflow
            notification_type: Type of notification

        Returns:
            Notification result
        """
        logger.info(f"Sending human task notification for task {task.id}")

        context = {
            "task_id": task.id,
            "task_title": task.title,
            "task_description": task.description,
            "assignee": task.assignee,
            "due_date": task.due_date.isoformat() if task.due_date else "Not specified",
            "instructions": task.instructions,
            "required_approvals": task.required_approvals
        }

        return await self.send_workflow_notification(
            notification_type, workflow, context
        )

    async def send_urgent_alert(
        self,
        workflow: RemediationWorkflow,
        issue_description: str,
        immediate_actions: List[str],
        time_constraint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send urgent alert for critical issues

        Args:
            workflow: The workflow with urgent issue
            issue_description: Description of the urgent issue
            immediate_actions: List of immediate actions required
            time_constraint: Time constraint if any

        Returns:
            Notification result
        """
        logger.warning(f"Sending urgent alert for workflow {workflow.id}: {issue_description}")

        context = {
            "urgent_issue": issue_description,
            "immediate_actions": "\n".join(f"• {action}" for action in immediate_actions),
            "time_constraint": time_constraint or "ASAP",
            "emergency_contact": "compliance-emergency@company.com",
            "escalation_procedure": "Follow emergency escalation protocol"
        }

        return await self.send_workflow_notification(
            NotificationType.URGENT_ATTENTION, workflow, context
        )

    async def send_deadline_reminder(
        self,
        task: HumanTask,
        workflow: RemediationWorkflow,
        hours_until_deadline: int
    ) -> Dict[str, Any]:
        """
        Send deadline reminder for human tasks

        Args:
            task: The task with approaching deadline
            workflow: Associated workflow
            hours_until_deadline: Hours until deadline

        Returns:
            Notification result
        """
        logger.info(f"Sending deadline reminder for task {task.id} ({hours_until_deadline}h remaining)")

        context = {
            "task_id": task.id,
            "task_title": task.title,
            "assignee": task.assignee,
            "hours_remaining": hours_until_deadline,
            "deadline_warning": f"Deadline in {hours_until_deadline} hours"
        }

        return await self.send_workflow_notification(
            NotificationType.DEADLINE_APPROACHING, workflow, context
        )

    def _determine_priority(
        self,
        notification_type: NotificationType,
        workflow: RemediationWorkflow
    ) -> NotificationPriority:
        """Determine notification priority"""

        # Urgent notifications
        if notification_type == NotificationType.URGENT_ATTENTION:
            return NotificationPriority.URGENT

        # Critical workflow priority
        if workflow.priority == RiskLevel.CRITICAL:
            return NotificationPriority.URGENT

        # High priority notifications
        high_priority_types = {
            NotificationType.WORKFLOW_FAILED,
            NotificationType.APPROVAL_NEEDED,
            NotificationType.DEADLINE_APPROACHING
        }

        if notification_type in high_priority_types or workflow.priority == RiskLevel.HIGH:
            return NotificationPriority.HIGH

        # Normal priority
        return NotificationPriority.NORMAL

    def _get_recipients(
        self,
        risk_level: RiskLevel,
        notification_type: NotificationType
    ) -> List[str]:
        """Get recipients based on risk level and notification type"""

        mapping = self.recipient_mappings.get(risk_level, {})
        roles = mapping.get("roles", ["compliance_team"])

        # Convert roles to actual recipients
        # In production, this would query a user directory
        recipient_map = {
            "dpo": "dpo@company.com",
            "compliance_manager": "compliance-manager@company.com",
            "compliance_team": "compliance-team@company.com",
            "security_team": "security-team@company.com"
        }

        return [recipient_map.get(role, role) for role in roles]

    def _determine_channels(
        self,
        priority: NotificationPriority,
        risk_level: RiskLevel
    ) -> List[NotificationChannel]:
        """Determine which channels to use"""

        mapping = self.recipient_mappings.get(risk_level, {})
        preferred_channels = mapping.get("channels", [NotificationChannel.EMAIL])

        # Filter by enabled channels
        enabled_channels = [
            channel for channel in preferred_channels
            if self.channel_configs.get(channel, {}).get("enabled", False)
        ]

        return enabled_channels or [NotificationChannel.EMAIL]

    def _prepare_notification_content(
        self,
        notification_type: NotificationType,
        workflow: RemediationWorkflow,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Prepare notification content"""

        template_config = self.templates.get(notification_type, {})
        subject_template = template_config.get("subject", "Remediation Notification")
        body_template = template_config.get("template", "Workflow notification for {workflow_id}")

        # Prepare template variables
        template_vars = {
            "workflow_id": workflow.id,
            "violation_description": workflow.metadata.get("violation_description", "N/A"),
            "remediation_type": workflow.remediation_type.value,
            "priority": workflow.priority.value,
            "started_at": workflow.created_at.isoformat() if workflow.created_at else "N/A",
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else "N/A",
            "risk_level": workflow.priority.value,
            "details_url": f"https://compliance.company.com/workflows/{workflow.id}",
            "action_url": f"https://compliance.company.com/workflows/{workflow.id}/actions",
            "approval_url": f"https://compliance.company.com/workflows/{workflow.id}/approve",
            "report_url": f"https://compliance.company.com/workflows/{workflow.id}/report",
            **context
        }

        # Format templates
        subject = subject_template.format(**template_vars)
        body = body_template.format(**template_vars)

        return {
            "subject": subject,
            "body": body,
            "template_vars": template_vars
        }

    async def _send_via_channel(
        self,
        channel: NotificationChannel,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send notification via specific channel"""

        try:
            if channel == NotificationChannel.EMAIL:
                return await self._send_email(content, recipients, priority)
            elif channel == NotificationChannel.SLACK:
                return await self._send_slack(content, recipients, priority)
            elif channel == NotificationChannel.SMS:
                return await self._send_sms(content, recipients, priority)
            elif channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook(content, recipients, priority)
            elif channel == NotificationChannel.IN_APP:
                return await self._send_in_app(content, recipients, priority)
            else:
                return {"success": False, "error": f"Unknown channel: {channel}"}

        except Exception as e:
            logger.error(f"Error sending via {channel}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _send_email(
        self,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send email notification (mock implementation)"""

        # In production, this would use an email service like SES, SendGrid, etc.
        logger.info(f"Sending email to {recipients}: {content['subject']}")

        # Simulate email sending
        await asyncio.sleep(0.1)

        return {
            "success": True,
            "channel": "email",
            "recipients": recipients,
            "message_id": f"email_{datetime.now(timezone.utc).timestamp()}",
            "delivery_time": datetime.now(timezone.utc).isoformat()
        }

    async def _send_slack(
        self,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send Slack notification (mock implementation)"""

        # In production, this would use Slack API
        logger.info(f"Sending Slack message to {recipients}: {content['subject']}")

        # Simulate Slack sending
        await asyncio.sleep(0.1)

        return {
            "success": True,
            "channel": "slack",
            "recipients": recipients,
            "message_id": f"slack_{datetime.now(timezone.utc).timestamp()}",
            "delivery_time": datetime.now(timezone.utc).isoformat()
        }

    async def _send_sms(
        self,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send SMS notification (mock implementation)"""

        # In production, this would use SMS service like Twilio
        logger.info(f"Sending SMS to {recipients}")

        # SMS has character limits
        sms_content = content['subject'][:160]

        return {
            "success": True,
            "channel": "sms",
            "recipients": recipients,
            "message_id": f"sms_{datetime.now(timezone.utc).timestamp()}",
            "content_length": len(sms_content),
            "delivery_time": datetime.now(timezone.utc).isoformat()
        }

    async def _send_webhook(
        self,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send webhook notification (mock implementation)"""

        # In production, this would POST to webhook URLs
        logger.info(f"Sending webhook notification")

        webhook_payload = {
            "notification": content,
            "recipients": recipients,
            "priority": priority.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return {
            "success": True,
            "channel": "webhook",
            "payload_size": len(str(webhook_payload)),
            "delivery_time": datetime.now(timezone.utc).isoformat()
        }

    async def _send_in_app(
        self,
        content: Dict[str, str],
        recipients: List[str],
        priority: NotificationPriority
    ) -> Dict[str, Any]:
        """Send in-app notification (mock implementation)"""

        # In production, this would store in database for app to display
        logger.info(f"Creating in-app notification for {recipients}")

        return {
            "success": True,
            "channel": "in_app",
            "recipients": recipients,
            "notification_id": f"app_{datetime.now(timezone.utc).timestamp()}",
            "created_time": datetime.now(timezone.utc).isoformat()
        }

    async def _log_notification(
        self,
        notification_type: NotificationType,
        workflow: RemediationWorkflow,
        results: Dict[str, Any]
    ):
        """Log notification for audit trail"""

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notification_type": notification_type.value,
            "workflow_id": workflow.id,
            "violation_id": workflow.violation_id,
            "results": results,
            "success": any(r.get("success", False) for r in results.values())
        }

        # In production, this would store in audit log
        logger.info(f"Notification logged: {log_entry}")

    async def schedule_deadline_reminders(
        self,
        task: HumanTask,
        workflow: RemediationWorkflow,
        reminder_hours: List[int] = None
    ) -> Dict[str, Any]:
        """
        Schedule deadline reminders for a human task

        Args:
            task: The human task
            workflow: Associated workflow
            reminder_hours: Hours before deadline to send reminders

        Returns:
            Scheduling result
        """
        reminder_hours = reminder_hours or [24, 4, 1]  # Default: 24h, 4h, 1h before

        if not task.due_date:
            return {"success": False, "error": "No due date set for task"}

        scheduled_reminders = []
        current_time = datetime.now(timezone.utc)

        for hours_before in reminder_hours:
            reminder_time = task.due_date - timedelta(hours=hours_before)

            if reminder_time > current_time:
                scheduled_reminders.append({
                    "reminder_time": reminder_time.isoformat(),
                    "hours_before_deadline": hours_before,
                    "scheduled": True
                })
            else:
                scheduled_reminders.append({
                    "reminder_time": reminder_time.isoformat(),
                    "hours_before_deadline": hours_before,
                    "scheduled": False,
                    "reason": "Past due"
                })

        # In production, this would integrate with a job scheduler
        logger.info(f"Scheduled {len([r for r in scheduled_reminders if r['scheduled']])} reminders for task {task.id}")

        return {
            "success": True,
            "task_id": task.id,
            "scheduled_reminders": scheduled_reminders,
            "total_scheduled": len([r for r in scheduled_reminders if r['scheduled']])
        }