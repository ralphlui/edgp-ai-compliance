"""
Comprehensive unit tests for SQSTool

Tests cover all SQSTool functionality including initialization, queue operations,
message operations, signal operations, and mock methods.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from botocore.exceptions import ClientError
import json
import os

from src.remediation_agent.tools.sqs_tool import SQSTool
from src.remediation_agent.state.models import RemediationSignal, SignalType


class TestBasics:
    """Test basic functionality"""

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_sqs_tool_creation(self, mock_settings):
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.test.com/main"
        mock_settings.sqs_dlq_url = "https://sqs.test.com/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            assert isinstance(tool, SQSTool)

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_get_all_configured_queues_returns_dict(self, mock_settings):
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.test.com/main"
        mock_settings.sqs_dlq_url = "https://sqs.test.com/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            queues = tool.get_all_configured_queues()
            assert isinstance(queues, dict)
            assert 'main_queue' in queues
            assert 'dlq' in queues


class TestInitialization:
    """Test SQSTool initialization"""

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_init_with_settings(self, mock_settings):
        """Test initialization with settings object"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123456789/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123456789/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            tool = SQSTool()
            
            assert tool.sqs_client is not None
            assert tool.region_name == "us-west-2"
            assert hasattr(tool, 'config')
            assert tool.config['main_queue_url'] == "https://sqs.us-west-2.amazonaws.com/123456789/main"

    @patch('src.remediation_agent.tools.sqs_tool.settings', None)
    @patch.dict(os.environ, {
        'AWS_REGION': 'eu-west-1',
        'SQS_MAIN_QUEUE_URL': 'https://sqs.eu-west-1.amazonaws.com/123/main',
        'SQS_DLQ_URL': 'https://sqs.eu-west-1.amazonaws.com/123/dlq'
    })
    def test_init_with_environment_variables(self):
        """Test initialization with environment variables"""
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            tool = SQSTool()
            
            assert tool.region_name == "eu-west-1"
            assert tool.config['main_queue_url'] == "https://sqs.eu-west-1.amazonaws.com/123/main"

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_initialize_client_failure_handles_gracefully(self, mock_settings):
        """Test client initialization handles errors gracefully"""
        mock_settings.aws_region = "us-east-1"
        mock_settings.sqs_main_queue_url = None
        mock_settings.sqs_dlq_url = None
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_boto.side_effect = Exception("AWS credentials not found")
            
            # Should not raise, but sqs_client should be None
            tool = SQSTool()
            assert tool.sqs_client is None


class TestUtilityMethods:
    """Test utility methods"""

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_get_queue_url_for_type_automatic(self, mock_settings):
        """Test getting queue URL for automatic remediation"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = "https://sqs.us-west-2.amazonaws.com/123/human"
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            url = tool.get_queue_url_for_type("automatic")
            assert url == "https://sqs.us-west-2.amazonaws.com/123/main"

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_get_queue_url_for_type_human_in_loop(self, mock_settings):
        """Test getting queue URL for human-in-the-loop"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = "https://sqs.us-west-2.amazonaws.com/123/human"
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            url = tool.get_queue_url_for_type("human_in_loop")
            assert url == "https://sqs.us-west-2.amazonaws.com/123/human"

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_get_queue_url_for_type_unknown(self, mock_settings):
        """Test getting queue URL for unknown type returns None"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            url = tool.get_queue_url_for_type("unknown_type")
            assert url is None

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_is_configured_with_queues(self, mock_settings):
        """Test is_configured returns True when properly configured"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client'):
            tool = SQSTool()
            tool.queue_urls = {'test': 'url'}  # Add a queue URL
            assert tool.is_configured() is True

    @patch('src.remediation_agent.tools.sqs_tool.settings')
    def test_is_configured_without_client(self, mock_settings):
        """Test is_configured returns False when client not initialized"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = None
        mock_settings.sqs_dlq_url = None
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client', side_effect=Exception("No credentials")):
            tool = SQSTool()
            assert tool.is_configured() is False


class TestMessageOperations:
    """Test async message operations"""

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_send_workflow_message_success(self, mock_settings):
        """Test successfully sending a workflow message"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.send_message = MagicMock(return_value={
                'MessageId': 'msg-123',
                'MD5OfMessageBody': 'abc123'
            })
            
            tool = SQSTool()
            queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
            message_data = {"action": "start_workflow", "workflow_id": "wf-001"}
            result = await tool.send_workflow_message(queue_url, message_data)
            
            assert result['success'] is True
            assert result['message_id'] == 'msg-123'

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_receive_workflow_messages_success(self, mock_settings):
        """Test successfully receiving workflow messages"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.receive_message = MagicMock(return_value={
                'Messages': [
                    {
                        'MessageId': 'msg-1',
                        'Body': json.dumps({"action": "execute"}),
                        'ReceiptHandle': 'receipt-1',
                        'MD5OfBody': 'abc123'
                    }
                ]
            })
            
            tool = SQSTool()
            queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
            result = await tool.receive_workflow_messages(queue_url, max_messages=1)
            
            assert result['success'] is True
            assert result['message_count'] == 1

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_delete_message_success(self, mock_settings):
        """Test successfully deleting a message"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.delete_message = MagicMock(return_value={})
            
            tool = SQSTool()
            queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
            result = await tool.delete_message(queue_url, "receipt-handle-123")
            
            assert result['success'] is True
            mock_client.delete_message.assert_called_once()


class TestCreateQueueOperations:
    """Test queue creation operations"""

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_create_remediation_queue_success(self, mock_settings):
        """Test successfully creating a remediation queue"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.create_queue = MagicMock(return_value={
                'QueueUrl': 'https://sqs.us-west-2.amazonaws.com/123/test-queue'
            })
            mock_client.get_queue_attributes = MagicMock(return_value={
                'Attributes': {'QueueArn': 'arn:aws:sqs:us-west-2:123:test-queue'}
            })
            mock_client.set_queue_attributes = MagicMock()
            
            tool = SQSTool()
            result = await tool.create_remediation_queue("test-queue", "wf-001")
            
            assert result['success'] is True
            assert 'queue_url' in result


class TestSerializationMethods:
    """Test serialization methods"""

    def test_serialize_remediation_signal(self):
        """Test serializing a remediation signal"""
        # Create a mock signal with required attributes
        signal = Mock()
        signal.signal_id = "sig-123"
        signal.violation_id = "viol-456"
        signal.activity_id = "act-789"
        signal.violation = None
        signal.activity = None
        signal.decision = None
        signal.validation = None
        signal.workflow_summary = None
        signal.metadata = {"key": "value"}
        
        # serialize_remediation_signal is an instance method, not a static method
        tool = SQSTool.__new__(SQSTool)  # Create instance without calling __init__
        serialized = tool.serialize_remediation_signal(signal)
        assert isinstance(serialized, str)
        
        data = json.loads(serialized)
        assert data['signal_id'] == "sig-123"
        assert data['violation_id'] == "viol-456"


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_send_message_with_no_client_uses_mock(self, mock_settings):
        """Test sending message when client is not initialized falls back to mock"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client', side_effect=Exception("No credentials")):
            tool = SQSTool()
            assert tool.sqs_client is None
            
            # Should use mock method
            result = await tool.send_workflow_message(
                "mock://queue",
                {"test": "data"}
            )
            
            # Mock method should return success with message_id (lowercase)
            assert 'message_id' in result
            assert result['mock'] is True

    @pytest.mark.asyncio
    @patch('src.remediation_agent.tools.sqs_tool.settings')
    async def test_receive_messages_empty_queue(self, mock_settings):
        """Test receiving messages from empty queue"""
        mock_settings.aws_region = "us-west-2"
        mock_settings.sqs_main_queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
        mock_settings.sqs_dlq_url = "https://sqs.us-west-2.amazonaws.com/123/dlq"
        mock_settings.sqs_high_priority_queue_url = None
        mock_settings.sqs_human_intervention_queue_url = None
        mock_settings.sqs_message_retention_period = 1209600
        mock_settings.sqs_visibility_timeout = 300
        mock_settings.sqs_receive_message_wait_time = 20
        mock_settings.sqs_max_receive_count = 3
        
        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            mock_client.receive_message = MagicMock(return_value={})
            
            tool = SQSTool()
            queue_url = "https://sqs.us-west-2.amazonaws.com/123/main"
            result = await tool.receive_workflow_messages(queue_url)
            
            assert result['success'] is True
            assert result['message_count'] == 0
