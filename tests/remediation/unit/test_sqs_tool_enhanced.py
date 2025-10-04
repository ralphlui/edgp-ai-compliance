"""
Enhanced unit tests for SQS tool with high coverage
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from src.remediation_agent.tools.sqs_tool import SQSTool
from src.remediation_agent.state.models import (
    RemediationWorkflow, WorkflowStep, RemediationType, WorkflowType, WorkflowStatus
)


class TestSQSToolEnhanced:
    """Enhanced tests for SQSTool with high coverage"""
    
    @pytest.fixture
    def sqs_tool(self):
        """Create an SQS tool instance"""
        return SQSTool()
    
    @pytest.fixture
    def sample_workflow(self):
        """Create a sample workflow"""
        return RemediationWorkflow(
            id="workflow-123",
            violation_id="violation-456",
            activity_id="activity-789",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="Update User Preference",
                    description="Update user consent preference",
                    action_type="api_call",
                    parameters={"endpoint": "/api/users/preferences", "method": "PUT"}
                )
            ],
            status=WorkflowStatus.PENDING
        )
    
    @pytest.mark.asyncio
    async def test_send_workflow_message_success(self, sqs_tool, sample_workflow):
        """Test successful workflow message sending"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.send_message.return_value = {
                'MessageId': 'msg-123',
                'MD5OfBody': 'abc123',
                'MD5OfMessageAttributes': 'def456'
            }
            
            result = await sqs_tool.send_workflow_message(sample_workflow, queue_url)
            
            assert result["success"] is True
            assert result["message_id"] == "msg-123"
            assert result["queue_url"] == queue_url
            
            # Verify send_message was called with correct parameters
            mock_sqs.send_message.assert_called_once()
            call_args = mock_sqs.send_message.call_args
            assert call_args[1]["QueueUrl"] == queue_url
            assert "MessageBody" in call_args[1]
            
            # Verify message body contains workflow data
            message_body = json.loads(call_args[1]["MessageBody"])
            assert message_body["workflow_id"] == sample_workflow.id
            assert message_body["violation_id"] == sample_workflow.violation_id
    
    @pytest.mark.asyncio
    async def test_send_workflow_message_failure(self, sqs_tool, sample_workflow):
        """Test workflow message sending failure"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.send_message.side_effect = Exception("SQS service unavailable")
            
            result = await sqs_tool.send_workflow_message(sample_workflow, queue_url)
            
            assert result["success"] is False
            assert "SQS service unavailable" in result["error"]
            assert result["queue_url"] == queue_url
    
    @pytest.mark.asyncio
    async def test_receive_workflow_messages_success(self, sqs_tool):
        """Test successful workflow message receiving"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            # Mock SQS response with messages
            mock_sqs.receive_message.return_value = {
                'Messages': [
                    {
                        'MessageId': 'msg-1',
                        'ReceiptHandle': 'receipt-1',
                        'Body': json.dumps({
                            'workflow_id': 'workflow-123',
                            'violation_id': 'violation-456',
                            'message_type': 'workflow_execution',
                            'timestamp': datetime.now().isoformat()
                        }),
                        'Attributes': {
                            'SentTimestamp': '1234567890'
                        }
                    },
                    {
                        'MessageId': 'msg-2',
                        'ReceiptHandle': 'receipt-2',
                        'Body': json.dumps({
                            'workflow_id': 'workflow-124',
                            'violation_id': 'violation-457',
                            'message_type': 'workflow_completion',
                            'timestamp': datetime.now().isoformat()
                        }),
                        'Attributes': {
                            'SentTimestamp': '1234567891'
                        }
                    }
                ]
            }
            
            result = await sqs_tool.receive_workflow_messages(queue_url, max_messages=2)
            
            assert result["success"] is True
            assert len(result["messages"]) == 2
            assert result["messages"][0]["message_id"] == "msg-1"
            assert result["messages"][0]["workflow_id"] == "workflow-123"
            assert result["messages"][1]["message_id"] == "msg-2"
            assert result["messages"][1]["workflow_id"] == "workflow-124"
            
            # Verify receive_message was called with correct parameters
            mock_sqs.receive_message.assert_called_once_with(
                QueueUrl=queue_url,
                MaxNumberOfMessages=2,
                WaitTimeSeconds=10,
                MessageAttributeNames=['All']
            )
    
    @pytest.mark.asyncio
    async def test_receive_workflow_messages_no_messages(self, sqs_tool):
        """Test receiving messages when queue is empty"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            # Mock empty SQS response
            mock_sqs.receive_message.return_value = {}
            
            result = await sqs_tool.receive_workflow_messages(queue_url)
            
            assert result["success"] is True
            assert len(result["messages"]) == 0
            assert result["queue_url"] == queue_url
    
    @pytest.mark.asyncio
    async def test_receive_workflow_messages_failure(self, sqs_tool):
        """Test workflow message receiving failure"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.receive_message.side_effect = Exception("Queue access denied")
            
            result = await sqs_tool.receive_workflow_messages(queue_url)
            
            assert result["success"] is False
            assert "Queue access denied" in result["error"]
    
    @pytest.mark.asyncio
    async def test_delete_message_success(self, sqs_tool):
        """Test successful message deletion"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        receipt_handle = "receipt-handle-123"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.delete_message.return_value = {}
            
            result = await sqs_tool.delete_message(queue_url, receipt_handle)
            
            assert result["success"] is True
            assert result["queue_url"] == queue_url
            assert result["receipt_handle"] == receipt_handle
            
            mock_sqs.delete_message.assert_called_once_with(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
    
    @pytest.mark.asyncio
    async def test_delete_message_failure(self, sqs_tool):
        """Test message deletion failure"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue"
        receipt_handle = "receipt-handle-123"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.delete_message.side_effect = Exception("Invalid receipt handle")
            
            result = await sqs_tool.delete_message(queue_url, receipt_handle)
            
            assert result["success"] is False
            assert "Invalid receipt handle" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_queue_success(self, sqs_tool):
        """Test successful queue creation"""
        queue_name = "test-remediation-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.create_queue.return_value = {
                'QueueUrl': f'https://sqs.us-east-1.amazonaws.com/123456789/{queue_name}'
            }
            
            result = await sqs_tool.create_queue(queue_name)
            
            assert result["success"] is True
            assert queue_name in result["queue_url"]
            assert result["queue_name"] == queue_name
            
            mock_sqs.create_queue.assert_called_once_with(
                QueueName=queue_name,
                Attributes={
                    'DelaySeconds': '0',
                    'MaxReceiveCount': '3',
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeoutSeconds': '300'     # 5 minutes
                }
            )
    
    @pytest.mark.asyncio
    async def test_create_queue_with_custom_attributes(self, sqs_tool):
        """Test queue creation with custom attributes"""
        queue_name = "custom-queue"
        custom_attributes = {
            'DelaySeconds': '5',
            'MessageRetentionPeriod': '604800',  # 7 days
            'VisibilityTimeoutSeconds': '600'    # 10 minutes
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.create_queue.return_value = {
                'QueueUrl': f'https://sqs.us-east-1.amazonaws.com/123456789/{queue_name}'
            }
            
            result = await sqs_tool.create_queue(queue_name, custom_attributes)
            
            assert result["success"] is True
            
            # Verify custom attributes were merged with defaults
            call_args = mock_sqs.create_queue.call_args
            attributes = call_args[1]["Attributes"]
            assert attributes['DelaySeconds'] == '5'
            assert attributes['MessageRetentionPeriod'] == '604800'
            assert attributes['VisibilityTimeoutSeconds'] == '600'
            assert attributes['MaxReceiveCount'] == '3'  # Default maintained
    
    @pytest.mark.asyncio
    async def test_create_queue_failure(self, sqs_tool):
        """Test queue creation failure"""
        queue_name = "test-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.create_queue.side_effect = Exception("Queue already exists")
            
            result = await sqs_tool.create_queue(queue_name)
            
            assert result["success"] is False
            assert "Queue already exists" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes_success(self, sqs_tool):
        """Test successful queue attributes retrieval"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.get_queue_attributes.return_value = {
                'Attributes': {
                    'ApproximateNumberOfMessages': '5',
                    'ApproximateNumberOfMessagesNotVisible': '2',
                    'DelaySeconds': '0',
                    'MessageRetentionPeriod': '1209600',
                    'QueueArn': 'arn:aws:sqs:us-east-1:123456789:test-queue'
                }
            }
            
            result = await sqs_tool.get_queue_attributes(queue_url)
            
            assert result["success"] is True
            assert result["attributes"]["ApproximateNumberOfMessages"] == "5"
            assert result["attributes"]["ApproximateNumberOfMessagesNotVisible"] == "2"
            assert result["queue_url"] == queue_url
            
            mock_sqs.get_queue_attributes.assert_called_once_with(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes_specific(self, sqs_tool):
        """Test queue attributes retrieval with specific attribute names"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        attribute_names = ['ApproximateNumberOfMessages', 'DelaySeconds']
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.get_queue_attributes.return_value = {
                'Attributes': {
                    'ApproximateNumberOfMessages': '3',
                    'DelaySeconds': '0'
                }
            }
            
            result = await sqs_tool.get_queue_attributes(queue_url, attribute_names)
            
            assert result["success"] is True
            assert len(result["attributes"]) == 2
            assert result["attributes"]["ApproximateNumberOfMessages"] == "3"
            
            mock_sqs.get_queue_attributes.assert_called_once_with(
                QueueUrl=queue_url,
                AttributeNames=attribute_names
            )
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes_failure(self, sqs_tool):
        """Test queue attributes retrieval failure"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/nonexistent-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.get_queue_attributes.side_effect = Exception("Queue does not exist")
            
            result = await sqs_tool.get_queue_attributes(queue_url)
            
            assert result["success"] is False
            assert "Queue does not exist" in result["error"]
    
    @pytest.mark.asyncio
    async def test_purge_queue_success(self, sqs_tool):
        """Test successful queue purging"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.purge_queue.return_value = {}
            
            result = await sqs_tool.purge_queue(queue_url)
            
            assert result["success"] is True
            assert result["queue_url"] == queue_url
            
            mock_sqs.purge_queue.assert_called_once_with(QueueUrl=queue_url)
    
    @pytest.mark.asyncio
    async def test_purge_queue_failure(self, sqs_tool):
        """Test queue purging failure"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        with patch('boto3.client') as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.return_value = mock_sqs
            
            mock_sqs.purge_queue.side_effect = Exception("PurgeQueueInProgress")
            
            result = await sqs_tool.purge_queue(queue_url)
            
            assert result["success"] is False
            assert "PurgeQueueInProgress" in result["error"]
    
    def test_serialize_workflow(self, sqs_tool, sample_workflow):
        """Test workflow serialization for SQS message"""
        serialized = sqs_tool._serialize_workflow(sample_workflow)
        
        assert isinstance(serialized, dict)
        assert serialized["workflow_id"] == sample_workflow.id
        assert serialized["violation_id"] == sample_workflow.violation_id
        assert serialized["activity_id"] == sample_workflow.activity_id
        assert serialized["remediation_type"] == sample_workflow.remediation_type.value
        assert serialized["workflow_type"] == sample_workflow.workflow_type.value
        assert serialized["status"] == sample_workflow.status.value
        assert len(serialized["steps"]) == len(sample_workflow.steps)
    
    def test_serialize_workflow_with_complex_steps(self, sqs_tool):
        """Test workflow serialization with complex steps"""
        workflow = RemediationWorkflow(
            id="complex-workflow",
            violation_id="violation-123",
            activity_id="activity-456",
            remediation_type=RemediationType.HUMAN_IN_LOOP,
            workflow_type=WorkflowType.HUMAN_IN_LOOP,
            steps=[
                WorkflowStep(
                    id="step-1",
                    name="Complex API Call",
                    description="Complex API operation",
                    action_type="api_call",
                    parameters={
                        "endpoint": "/api/complex",
                        "method": "POST",
                        "data": {"nested": {"key": "value"}},
                        "headers": {"Authorization": "Bearer token"}
                    }
                ),
                WorkflowStep(
                    id="step-2",
                    name="Database Operation",
                    description="Complex database operation",
                    action_type="database_operation",
                    parameters={
                        "query": "UPDATE users SET status = ? WHERE id IN (?, ?)",
                        "params": ["inactive", "user1", "user2"]
                    }
                )
            ]
        )
        
        serialized = sqs_tool._serialize_workflow(workflow)
        
        assert len(serialized["steps"]) == 2
        assert serialized["steps"][0]["parameters"]["data"]["nested"]["key"] == "value"
        assert serialized["steps"][1]["parameters"]["params"] == ["inactive", "user1", "user2"]
    
    def test_deserialize_message_body_valid(self, sqs_tool):
        """Test message body deserialization with valid JSON"""
        message_body = json.dumps({
            "workflow_id": "workflow-123",
            "violation_id": "violation-456",
            "message_type": "workflow_execution",
            "timestamp": "2024-01-15T10:30:00Z"
        })
        
        result = sqs_tool._deserialize_message_body(message_body)
        
        assert result["workflow_id"] == "workflow-123"
        assert result["violation_id"] == "violation-456"
        assert result["message_type"] == "workflow_execution"
        assert result["timestamp"] == "2024-01-15T10:30:00Z"
    
    def test_deserialize_message_body_invalid_json(self, sqs_tool):
        """Test message body deserialization with invalid JSON"""
        message_body = "Invalid JSON content"
        
        result = sqs_tool._deserialize_message_body(message_body)
        
        assert result == {}  # Should return empty dict for invalid JSON
    
    def test_create_message_attributes(self, sqs_tool, sample_workflow):
        """Test message attributes creation"""
        attributes = sqs_tool._create_message_attributes(sample_workflow)
        
        assert "WorkflowId" in attributes
        assert attributes["WorkflowId"]["StringValue"] == sample_workflow.id
        assert attributes["WorkflowId"]["DataType"] == "String"
        
        assert "ViolationId" in attributes
        assert attributes["ViolationId"]["StringValue"] == sample_workflow.violation_id
        
        assert "RemediationType" in attributes
        assert attributes["RemediationType"]["StringValue"] == sample_workflow.remediation_type.value
        
        assert "Priority" in attributes
        assert attributes["Priority"]["StringValue"] == sample_workflow.priority.value
    
    def test_create_message_attributes_with_metadata(self, sqs_tool):
        """Test message attributes creation with workflow metadata"""
        workflow = RemediationWorkflow(
            id="workflow-with-metadata",
            violation_id="violation-123",
            activity_id="activity-456",
            remediation_type=RemediationType.AUTOMATIC,
            workflow_type=WorkflowType.AUTOMATIC,
            metadata={
                "source": "compliance_engine",
                "urgency": "high",
                "retry_count": 0
            }
        )
        
        attributes = sqs_tool._create_message_attributes(workflow)
        
        assert "Source" in attributes
        assert attributes["Source"]["StringValue"] == "compliance_engine"
        
        assert "Urgency" in attributes
        assert attributes["Urgency"]["StringValue"] == "high"
        
        assert "RetryCount" in attributes
        assert attributes["RetryCount"]["StringValue"] == "0"
        assert attributes["RetryCount"]["DataType"] == "Number"
    
    def test_format_message_for_logging(self, sqs_tool):
        """Test message formatting for logging"""
        message = {
            "MessageId": "msg-123",
            "workflow_id": "workflow-456",
            "violation_id": "violation-789",
            "message_type": "workflow_execution"
        }
        
        formatted = sqs_tool._format_message_for_logging(message)
        
        assert formatted["message_id"] == "msg-123"
        assert formatted["workflow_id"] == "workflow-456"
        assert formatted["violation_id"] == "violation-789"
        assert formatted["message_type"] == "workflow_execution"
        assert "timestamp" in formatted
    
    def test_format_message_for_logging_minimal(self, sqs_tool):
        """Test message formatting with minimal data"""
        message = {
            "MessageId": "msg-456"
        }
        
        formatted = sqs_tool._format_message_for_logging(message)
        
        assert formatted["message_id"] == "msg-456"
        assert formatted["workflow_id"] is None
        assert formatted["violation_id"] is None
        assert "timestamp" in formatted
    
    def test_validate_queue_url_valid(self, sqs_tool):
        """Test queue URL validation with valid URLs"""
        valid_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789/test-queue",
            "https://sqs.eu-west-1.amazonaws.com/987654321/production-queue",
            "https://sqs.ap-northeast-1.amazonaws.com/111222333/dev-queue"
        ]
        
        for url in valid_urls:
            assert sqs_tool._validate_queue_url(url) is True
    
    def test_validate_queue_url_invalid(self, sqs_tool):
        """Test queue URL validation with invalid URLs"""
        invalid_urls = [
            "http://invalid-url.com/queue",
            "https://not-sqs.amazonaws.com/123/queue",
            "https://sqs.amazonaws.com/invalid",
            "",
            None,
            123
        ]
        
        for url in invalid_urls:
            assert sqs_tool._validate_queue_url(url) is False
    
    def test_extract_queue_name_from_url(self, sqs_tool):
        """Test queue name extraction from URL"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/my-remediation-queue"
        
        queue_name = sqs_tool._extract_queue_name_from_url(queue_url)
        
        assert queue_name == "my-remediation-queue"
    
    def test_extract_queue_name_from_invalid_url(self, sqs_tool):
        """Test queue name extraction from invalid URL"""
        invalid_url = "https://invalid-url.com/not-a-queue"
        
        queue_name = sqs_tool._extract_queue_name_from_url(invalid_url)
        
        assert queue_name is None
    
    def test_get_default_queue_attributes(self, sqs_tool):
        """Test default queue attributes"""
        defaults = sqs_tool._get_default_queue_attributes()
        
        assert defaults["DelaySeconds"] == "0"
        assert defaults["MaxReceiveCount"] == "3"
        assert defaults["MessageRetentionPeriod"] == "1209600"  # 14 days
        assert defaults["VisibilityTimeoutSeconds"] == "300"     # 5 minutes
    
    def test_merge_queue_attributes(self, sqs_tool):
        """Test queue attributes merging"""
        custom_attributes = {
            "DelaySeconds": "10",
            "CustomAttribute": "value"
        }
        
        merged = sqs_tool._merge_queue_attributes(custom_attributes)
        
        # Custom value should override default
        assert merged["DelaySeconds"] == "10"
        # Custom attribute should be included
        assert merged["CustomAttribute"] == "value"
        # Default values should be preserved
        assert merged["MaxReceiveCount"] == "3"
        assert merged["MessageRetentionPeriod"] == "1209600"


class TestSQSToolEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def sqs_tool(self):
        return SQSTool()
    
    @pytest.mark.asyncio
    async def test_send_workflow_message_none_workflow(self, sqs_tool):
        """Test sending message with None workflow"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        result = await sqs_tool.send_workflow_message(None, queue_url)
        
        assert result["success"] is False
        assert "workflow cannot be None" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_send_workflow_message_invalid_queue_url(self, sqs_tool, sample_workflow):
        """Test sending message with invalid queue URL"""
        invalid_url = "invalid-queue-url"
        
        result = await sqs_tool.send_workflow_message(sample_workflow, invalid_url)
        
        assert result["success"] is False
        assert "invalid queue url" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_receive_workflow_messages_invalid_max_messages(self, sqs_tool):
        """Test receiving messages with invalid max_messages parameter"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        # Test with 0 messages
        result = await sqs_tool.receive_workflow_messages(queue_url, max_messages=0)
        assert result["success"] is False
        
        # Test with too many messages
        result = await sqs_tool.receive_workflow_messages(queue_url, max_messages=15)
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_delete_message_empty_receipt_handle(self, sqs_tool):
        """Test deleting message with empty receipt handle"""
        queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        
        result = await sqs_tool.delete_message(queue_url, "")
        
        assert result["success"] is False
        assert "receipt handle cannot be empty" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_create_queue_empty_name(self, sqs_tool):
        """Test creating queue with empty name"""
        result = await sqs_tool.create_queue("")
        
        assert result["success"] is False
        assert "queue name cannot be empty" in result["error"].lower()
    
    def test_serialize_workflow_none(self, sqs_tool):
        """Test serializing None workflow"""
        result = sqs_tool._serialize_workflow(None)
        
        assert result == {}
    
    def test_deserialize_message_body_none(self, sqs_tool):
        """Test deserializing None message body"""
        result = sqs_tool._deserialize_message_body(None)
        
        assert result == {}
    
    def test_create_message_attributes_none_workflow(self, sqs_tool):
        """Test creating message attributes with None workflow"""
        result = sqs_tool._create_message_attributes(None)
        
        assert result == {}
    
    def test_extract_queue_name_from_none_url(self, sqs_tool):
        """Test extracting queue name from None URL"""
        result = sqs_tool._extract_queue_name_from_url(None)
        
        assert result is None