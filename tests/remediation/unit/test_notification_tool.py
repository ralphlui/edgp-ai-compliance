"""
Unit tests for notification tool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime

from src.remediation_agent.tools.notification_tool import NotificationTool
from src.remediation_agent.state.models import RemediationSignal, WorkflowStep
from src.compliance_agent.models.compliance_models import RiskLevel


class TestNotificationTool:
    """Test NotificationTool class"""
    
    @pytest.fixture
    def notification_tool(self):
        """Create a notification tool instance for testing"""
        return NotificationTool()
    
    @pytest.mark.asyncio
    async def test_send_workflow_started_notification(self, notification_tool, sample_remediation_signal):
        """Test sending workflow started notification"""
        workflow_id = "workflow-123"
        
        with patch.object(notification_tool, '_send_email') as mock_send_email, \
             patch.object(notification_tool, '_send_slack_message') as mock_send_slack:
            
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            mock_send_slack.return_value = {"success": True, "ts": "slack-123"}
            
            result = await notification_tool.send_workflow_started_notification(
                sample_remediation_signal, workflow_id
            )
            
            assert result["success"] is True
            assert "notifications_sent" in result
            assert len(result["notifications_sent"]) > 0
    
    @pytest.mark.asyncio
    async def test_send_workflow_completed_notification(self, notification_tool, sample_remediation_signal):
        """Test sending workflow completed notification"""
        workflow_id = "workflow-123"
        steps_completed = 3
        total_duration = 150  # seconds
        
        with patch.object(notification_tool, '_send_email') as mock_send_email:
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            
            result = await notification_tool.send_workflow_completed_notification(
                sample_remediation_signal, workflow_id, steps_completed, total_duration
            )
            
            assert result["success"] is True
            assert "completion_time" in result
    
    @pytest.mark.asyncio
    async def test_send_workflow_failed_notification(self, notification_tool, sample_remediation_signal):
        """Test sending workflow failed notification"""
        workflow_id = "workflow-123"
        error_message = "Database connection failed"
        failed_step = "Delete user data"
        
        with patch.object(notification_tool, '_send_email') as mock_send_email, \
             patch.object(notification_tool, '_send_slack_message') as mock_send_slack:
            
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            mock_send_slack.return_value = {"success": True, "ts": "slack-123"}
            
            result = await notification_tool.send_workflow_failed_notification(
                sample_remediation_signal, workflow_id, error_message, failed_step
            )
            
            assert result["success"] is True
            assert "error_details" in result
            assert result["error_details"]["failed_step"] == failed_step
    
    @pytest.mark.asyncio
    async def test_send_approval_required_notification(self, notification_tool, sample_remediation_signal):
        """Test sending approval required notification"""
        workflow_id = "workflow-123"
        pending_step = "Delete user personal data"
        approval_url = "https://app.company.com/approve/workflow-123"
        
        with patch.object(notification_tool, '_send_email') as mock_send_email:
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            
            result = await notification_tool.send_approval_required_notification(
                sample_remediation_signal, workflow_id, pending_step, approval_url
            )
            
            assert result["success"] is True
            assert "approval_details" in result
            assert result["approval_details"]["approval_url"] == approval_url
    
    @pytest.mark.asyncio
    async def test_send_step_completed_notification(self, notification_tool, sample_workflow_steps):
        """Test sending step completed notification"""
        completed_step = sample_workflow_steps[0]
        workflow_id = "workflow-123"
        
        with patch.object(notification_tool, '_send_email') as mock_send_email:
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            
            result = await notification_tool.send_step_completed_notification(
                completed_step, workflow_id
            )
            
            assert result["success"] is True
            assert "step_details" in result
    
    @pytest.mark.asyncio
    async def test_send_compliance_violation_alert(self, notification_tool, sample_remediation_signal):
        """Test sending compliance violation alert"""
        with patch.object(notification_tool, '_send_email') as mock_send_email, \
             patch.object(notification_tool, '_send_slack_message') as mock_send_slack:
            
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            mock_send_slack.return_value = {"success": True, "ts": "slack-123"}
            
            result = await notification_tool.send_compliance_violation_alert(sample_remediation_signal)
            
            assert result["success"] is True
            assert "alert_severity" in result
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, notification_tool):
        """Test successful email sending"""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.send_message.return_value = {}
            
            result = await notification_tool._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                body="Test Body",
                is_html=False
            )
            
            assert result["success"] is True
            assert "message_id" in result
    
    @pytest.mark.asyncio
    async def test_send_email_smtp_error(self, notification_tool):
        """Test email sending with SMTP error"""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP server unavailable")
            
            result = await notification_tool._send_email(
                to_email="test@example.com",
                subject="Test Subject",
                body="Test Body"
            )
            
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_send_html_email(self, notification_tool):
        """Test sending HTML email"""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.send_message.return_value = {}
            
            html_body = "<h1>Test HTML</h1><p>This is a test email.</p>"
            
            result = await notification_tool._send_email(
                to_email="test@example.com",
                subject="HTML Test",
                body=html_body,
                is_html=True
            )
            
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_send_slack_message_success(self, notification_tool):
        """Test successful Slack message sending"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"ok": True, "ts": "1234567890.123"}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await notification_tool._send_slack_message(
                channel="#alerts",
                message="Test message",
                username="ComplianceBot"
            )
            
            assert result["success"] is True
            assert result["ts"] == "1234567890.123"
    
    @pytest.mark.asyncio
    async def test_send_slack_message_error(self, notification_tool):
        """Test Slack message sending with error"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json.return_value = {"ok": False, "error": "channel_not_found"}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await notification_tool._send_slack_message(
                channel="#invalid-channel",
                message="Test message"
            )
            
            assert result["success"] is False
            assert "error" in result
    
    def test_create_workflow_started_email_template(self, notification_tool, sample_remediation_signal):
        """Test creation of workflow started email template"""
        workflow_id = "workflow-123"
        
        subject, body = notification_tool._create_workflow_started_email_template(
            sample_remediation_signal, workflow_id
        )
        
        assert "Remediation Workflow Started" in subject
        assert workflow_id in body
        assert sample_remediation_signal.violation.violation_type in body
        assert sample_remediation_signal.violation.id in body
    
    def test_create_workflow_completed_email_template(self, notification_tool, sample_remediation_signal):
        """Test creation of workflow completed email template"""
        workflow_id = "workflow-123"
        steps_completed = 3
        duration = 150
        
        subject, body = notification_tool._create_workflow_completed_email_template(
            sample_remediation_signal, workflow_id, steps_completed, duration
        )
        
        assert "Completed Successfully" in subject
        assert str(steps_completed) in body
        assert str(duration) in body
        assert workflow_id in body
    
    def test_create_workflow_failed_email_template(self, notification_tool, sample_remediation_signal):
        """Test creation of workflow failed email template"""
        workflow_id = "workflow-123"
        error_message = "Database connection failed"
        failed_step = "Delete user data"
        
        subject, body = notification_tool._create_workflow_failed_email_template(
            sample_remediation_signal, workflow_id, error_message, failed_step
        )
        
        assert "Failed" in subject
        assert error_message in body
        assert failed_step in body
        assert workflow_id in body
    
    def test_create_approval_required_email_template(self, notification_tool, sample_remediation_signal):
        """Test creation of approval required email template"""
        workflow_id = "workflow-123"
        pending_step = "Delete user personal data"
        approval_url = "https://app.company.com/approve/workflow-123"
        
        subject, body = notification_tool._create_approval_required_email_template(
            sample_remediation_signal, workflow_id, pending_step, approval_url
        )
        
        assert "Approval Required" in subject
        assert pending_step in body
        assert approval_url in body
        assert workflow_id in body
    
    def test_create_compliance_violation_alert_template(self, notification_tool, sample_remediation_signal):
        """Test creation of compliance violation alert template"""
        subject, body = notification_tool._create_compliance_violation_alert_template(
            sample_remediation_signal
        )
        
        assert "Compliance Violation Detected" in subject
        assert sample_remediation_signal.violation.violation_type in body
        assert sample_remediation_signal.violation.risk_level.value in body
        assert sample_remediation_signal.violation.id in body
    
    def test_create_slack_workflow_message(self, notification_tool, sample_remediation_signal):
        """Test creation of Slack workflow message"""
        workflow_id = "workflow-123"
        status = "started"
        
        message = notification_tool._create_slack_workflow_message(
            sample_remediation_signal, workflow_id, status
        )
        
        assert workflow_id in message
        assert status in message
        assert sample_remediation_signal.violation.violation_type in message
    
    def test_create_slack_alert_message(self, notification_tool, sample_remediation_signal):
        """Test creation of Slack alert message"""
        message = notification_tool._create_slack_alert_message(sample_remediation_signal)
        
        assert "🚨" in message  # Alert emoji
        assert sample_remediation_signal.violation.violation_type in message
        assert sample_remediation_signal.violation.risk_level.value in message
    
    def test_determine_notification_recipients_critical_risk(self, notification_tool, sample_remediation_signal):
        """Test notification recipients for critical risk level"""
        sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL
        
        recipients = notification_tool._determine_notification_recipients(sample_remediation_signal)
        
        assert "compliance@company.com" in recipients["email"]
        assert "legal@company.com" in recipients["email"]
        assert "#critical-alerts" in recipients["slack"]
    
    def test_determine_notification_recipients_low_risk(self, notification_tool, sample_remediation_signal):
        """Test notification recipients for low risk level"""
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        
        recipients = notification_tool._determine_notification_recipients(sample_remediation_signal)
        
        assert "compliance@company.com" in recipients["email"]
        assert len(recipients["email"]) <= 2  # Fewer recipients for low risk
        assert "#general-alerts" in recipients["slack"]
    
    def test_determine_alert_severity_critical(self, notification_tool, sample_remediation_signal):
        """Test alert severity determination for critical risk"""
        sample_remediation_signal.violation.risk_level = RiskLevel.CRITICAL
        
        severity = notification_tool._determine_alert_severity(sample_remediation_signal)
        
        assert severity == "critical"
    
    def test_determine_alert_severity_low(self, notification_tool, sample_remediation_signal):
        """Test alert severity determination for low risk"""
        sample_remediation_signal.violation.risk_level = RiskLevel.LOW
        
        severity = notification_tool._determine_alert_severity(sample_remediation_signal)
        
        assert severity == "low"
    
    def test_format_duration(self, notification_tool):
        """Test duration formatting for human readability"""
        # Test seconds
        assert notification_tool._format_duration(45) == "45 seconds"
        
        # Test minutes
        assert notification_tool._format_duration(150) == "2 minutes, 30 seconds"
        
        # Test hours
        assert notification_tool._format_duration(7200) == "2 hours"
        
        # Test complex duration
        assert notification_tool._format_duration(3723) == "1 hour, 2 minutes, 3 seconds"
    
    def test_format_risk_level_display(self, notification_tool):
        """Test risk level formatting for display"""
        assert notification_tool._format_risk_level_display(RiskLevel.CRITICAL) == "🔴 CRITICAL"
        assert notification_tool._format_risk_level_display(RiskLevel.HIGH) == "🟡 HIGH"
        assert notification_tool._format_risk_level_display(RiskLevel.MEDIUM) == "🟠 MEDIUM"
        assert notification_tool._format_risk_level_display(RiskLevel.LOW) == "🟢 LOW"
    
    @pytest.mark.asyncio
    async def test_batch_send_notifications(self, notification_tool, sample_remediation_signal):
        """Test batch sending of multiple notifications"""
        notifications = [
            {
                "type": "email",
                "to": "test1@example.com",
                "subject": "Test 1",
                "body": "Test body 1"
            },
            {
                "type": "email", 
                "to": "test2@example.com",
                "subject": "Test 2",
                "body": "Test body 2"
            },
            {
                "type": "slack",
                "channel": "#alerts",
                "message": "Test slack message"
            }
        ]
        
        with patch.object(notification_tool, '_send_email') as mock_send_email, \
             patch.object(notification_tool, '_send_slack_message') as mock_send_slack:
            
            mock_send_email.return_value = {"success": True, "message_id": "email-123"}
            mock_send_slack.return_value = {"success": True, "ts": "slack-123"}
            
            result = await notification_tool.batch_send_notifications(notifications)
            
            assert result["success"] is True
            assert len(result["results"]) == 3
            assert mock_send_email.call_count == 2
            assert mock_send_slack.call_count == 1
    
    @pytest.mark.asyncio
    async def test_send_notification_digest(self, notification_tool):
        """Test sending daily/weekly notification digest"""
        digest_data = {
            "period": "daily",
            "workflows_completed": 15,
            "workflows_failed": 2,
            "violations_processed": 20,
            "average_completion_time": 180
        }
        
        with patch.object(notification_tool, '_send_email') as mock_send_email:
            mock_send_email.return_value = {"success": True, "message_id": "digest-123"}
            
            result = await notification_tool.send_notification_digest(digest_data)
            
            assert result["success"] is True
            assert "digest_period" in result