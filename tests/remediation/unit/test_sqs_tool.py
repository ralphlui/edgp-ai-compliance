"""
Unit tests for SQS tool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from typing import Dict, Any

from src.remediation_agent.tools.sqs_tool import SQSTool
from src.remediation_agent.state.models import RemediationSignal


class TestSQSTool:
    """Test SQSTool class"""
    
    @pytest.fixture
    def sqs_tool(self):
        """Create an SQS tool instance for testing"""
        with patch.dict('os.environ', {
            'AWS_REGION': 'us-west-2',
            'SQS_REMEDIATION_QUEUE_URL': 'https://sqs.us-west-2.amazonaws.com/123456789/remediation-queue'
        }):
            return SQSTool()
    
    @pytest.mark.asyncio
    async def test_send_remediation_signal_success(self, sqs_tool, sample_remediation_signal):
        """Test successful sending of remediation signal to SQS"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message.return_value = {
                'MessageId': 'test-message-id-123',
                'MD5OfBody': 'test-md5-hash'
            }
            
            result = await sqs_tool.send_remediation_signal(sample_remediation_signal)
            
            assert result["success"] is True
            assert result["message_id"] == "test-message-id-123"
            assert "queue_url" in result
            
            # Verify SQS send_message was called correctly
            mock_sqs.send_message.assert_called_once()
            call_args = mock_sqs.send_message.call_args
            assert call_args[1]["QueueUrl"] == sqs_tool.queue_url
            
            # Verify message body contains serialized signal
            message_body = json.loads(call_args[1]["MessageBody"])
            assert message_body["violation_id"] == sample_remediation_signal.violation.id
    
    @pytest.mark.asyncio
    async def test_send_remediation_signal_with_delay(self, sqs_tool, sample_remediation_signal):
        """Test sending remediation signal with delay"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message.return_value = {
                'MessageId': 'test-message-id-123',
                'MD5OfBody': 'test-md5-hash'
            }
            
            delay_seconds = 300  # 5 minutes
            result = await sqs_tool.send_remediation_signal(sample_remediation_signal, delay_seconds=delay_seconds)
            
            assert result["success"] is True
            
            # Verify delay was set correctly
            call_args = mock_sqs.send_message.call_args
            assert call_args[1]["DelaySeconds"] == delay_seconds
    
    @pytest.mark.asyncio
    async def test_send_remediation_signal_with_priority(self, sqs_tool, sample_remediation_signal):
        """Test sending remediation signal with priority attributes"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message.return_value = {
                'MessageId': 'test-message-id-123',
                'MD5OfBody': 'test-md5-hash'
            }
            
            priority = "high"
            result = await sqs_tool.send_remediation_signal(sample_remediation_signal, priority=priority)
            
            assert result["success"] is True
            
            # Verify message attributes include priority
            call_args = mock_sqs.send_message.call_args
            message_attributes = call_args[1]["MessageAttributes"]
            assert "Priority" in message_attributes
            assert message_attributes["Priority"]["StringValue"] == priority
    
    @pytest.mark.asyncio
    async def test_send_remediation_signal_boto3_error(self, sqs_tool, sample_remediation_signal):
        """Test handling of boto3 errors when sending message"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message.side_effect = Exception("SQS service unavailable")
            
            result = await sqs_tool.send_remediation_signal(sample_remediation_signal)
            
            assert result["success"] is False
            assert "error" in result
            assert "SQS service unavailable" in result["error"]
    
    @pytest.mark.asyncio
    async def test_receive_remediation_signals_success(self, sqs_tool):
        """Test successful receiving of remediation signals from SQS"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.receive_message.return_value = {
                'Messages': [
                    {
                        'MessageId': 'msg-1',
                        'ReceiptHandle': 'receipt-1',
                        'Body': json.dumps({
                            'violation_id': 'test-violation-1',
                            'timestamp': '2024-01-01T00:00:00Z',
                            'priority': 'high'
                        }),
                        'Attributes': {'SentTimestamp': '1609459200'}
                    },
                    {
                        'MessageId': 'msg-2',
                        'ReceiptHandle': 'receipt-2',
                        'Body': json.dumps({
                            'violation_id': 'test-violation-2',
                            'timestamp': '2024-01-01T01:00:00Z',
                            'priority': 'medium'
                        }),
                        'Attributes': {'SentTimestamp': '1609462800'}
                    }
                ]
            }
            
            result = await sqs_tool.receive_remediation_signals(max_messages=2)
            
            assert result["success"] is True
            assert len(result["messages"]) == 2
            assert result["messages"][0]["message_id"] == "msg-1"
            assert result["messages"][1]["message_id"] == "msg-2"
    
    @pytest.mark.asyncio
    async def test_receive_remediation_signals_no_messages(self, sqs_tool):
        """Test receiving when no messages are available"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.receive_message.return_value = {}  # No messages
            
            result = await sqs_tool.receive_remediation_signals()
            
            assert result["success"] is True
            assert len(result["messages"]) == 0
    
    @pytest.mark.asyncio
    async def test_receive_remediation_signals_with_wait_time(self, sqs_tool):
        """Test receiving messages with long polling"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.receive_message.return_value = {}
            
            wait_time = 20
            await sqs_tool.receive_remediation_signals(wait_time_seconds=wait_time)
            
            # Verify long polling was used
            call_args = mock_sqs.receive_message.call_args
            assert call_args[1]["WaitTimeSeconds"] == wait_time
    
    @pytest.mark.asyncio
    async def test_delete_message_success(self, sqs_tool):
        """Test successful message deletion"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.delete_message.return_value = {}
            
            receipt_handle = "test-receipt-handle"
            result = await sqs_tool.delete_message(receipt_handle)
            
            assert result["success"] is True
            
            # Verify delete_message was called correctly
            mock_sqs.delete_message.assert_called_once_with(
                QueueUrl=sqs_tool.queue_url,
                ReceiptHandle=receipt_handle
            )
    
    @pytest.mark.asyncio
    async def test_delete_message_error(self, sqs_tool):
        """Test handling of delete message errors"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.delete_message.side_effect = Exception("Message not found")
            
            result = await sqs_tool.delete_message("invalid-receipt-handle")
            
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes(self, sqs_tool):
        """Test getting queue attributes"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.get_queue_attributes.return_value = {
                'Attributes': {
                    'ApproximateNumberOfMessages': '5',
                    'ApproximateNumberOfMessagesNotVisible': '2',
                    'VisibilityTimeout': '300',
                    'MessageRetentionPeriod': '1209600'
                }
            }
            
            result = await sqs_tool.get_queue_attributes()
            
            assert result["success"] is True
            assert result["attributes"]["ApproximateNumberOfMessages"] == '5'
            assert result["attributes"]["VisibilityTimeout"] == '300'
    
    def test_serialize_remediation_signal(self, sqs_tool, sample_remediation_signal):
        """Test serialization of remediation signal for SQS"""
        serialized = sqs_tool._serialize_remediation_signal(sample_remediation_signal)
        
        assert isinstance(serialized, str)
        
        # Verify it can be deserialized
        data = json.loads(serialized)
        assert data["violation_id"] == sample_remediation_signal.violation.id
        assert data["timestamp"] is not None
        assert "violation" in data
        assert "context" in data
    
    def test_create_message_attributes_with_priority(self, sqs_tool):
        """Test creation of message attributes with priority"""
        priority = "high"
        attributes = sqs_tool._create_message_attributes(priority=priority)
        
        assert "Priority" in attributes
        assert attributes["Priority"]["DataType"] == "String"
        assert attributes["Priority"]["StringValue"] == priority
    
    def test_create_message_attributes_with_violation_type(self, sqs_tool, sample_remediation_signal):
        """Test creation of message attributes with violation type"""
        attributes = sqs_tool._create_message_attributes(
            remediation_signal=sample_remediation_signal
        )
        
        assert "ViolationType" in attributes
        assert attributes["ViolationType"]["DataType"] == "String"
        assert attributes["ViolationType"]["StringValue"] == sample_remediation_signal.violation.violation_type
    
    def test_create_message_attributes_with_risk_level(self, sqs_tool, sample_remediation_signal):
        """Test creation of message attributes with risk level"""
        attributes = sqs_tool._create_message_attributes(
            remediation_signal=sample_remediation_signal
        )
        
        assert "RiskLevel" in attributes
        assert attributes["RiskLevel"]["DataType"] == "String"
        assert attributes["RiskLevel"]["StringValue"] == sample_remediation_signal.violation.risk_level.value
    
    def test_create_message_attributes_minimal(self, sqs_tool):
        """Test creation of minimal message attributes"""
        attributes = sqs_tool._create_message_attributes()
        
        # Should always include timestamp
        assert "Timestamp" in attributes
        assert attributes["Timestamp"]["DataType"] == "String"
    
    @pytest.mark.asyncio
    async def test_batch_send_remediation_signals(self, sqs_tool, sample_remediation_signal):
        """Test batch sending of multiple remediation signals"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message_batch.return_value = {
                'Successful': [
                    {'Id': '1', 'MessageId': 'msg-1', 'MD5OfBody': 'hash-1'},
                    {'Id': '2', 'MessageId': 'msg-2', 'MD5OfBody': 'hash-2'}
                ],
                'Failed': []
            }
            
            signals = [sample_remediation_signal, sample_remediation_signal]
            result = await sqs_tool.batch_send_remediation_signals(signals)
            
            assert result["success"] is True
            assert len(result["successful"]) == 2
            assert len(result["failed"]) == 0
    
    @pytest.mark.asyncio
    async def test_batch_send_with_failures(self, sqs_tool, sample_remediation_signal):
        """Test batch sending with some failures"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.send_message_batch.return_value = {
                'Successful': [
                    {'Id': '1', 'MessageId': 'msg-1', 'MD5OfBody': 'hash-1'}
                ],
                'Failed': [
                    {'Id': '2', 'Code': 'InvalidMessage', 'Message': 'Message too large'}
                ]
            }
            
            signals = [sample_remediation_signal, sample_remediation_signal]
            result = await sqs_tool.batch_send_remediation_signals(signals)
            
            assert result["success"] is False  # Partial failure
            assert len(result["successful"]) == 1
            assert len(result["failed"]) == 1
            assert result["failed"][0]["Code"] == "InvalidMessage"
    
    def test_queue_url_configuration(self, sqs_tool):
        """Test that queue URL is properly configured"""
        assert sqs_tool.queue_url is not None
        assert "sqs" in sqs_tool.queue_url
        assert "remediation" in sqs_tool.queue_url
    
    def test_aws_region_configuration(self, sqs_tool):
        """Test that AWS region is properly configured"""
        assert sqs_tool.region is not None
        assert len(sqs_tool.region) > 0
    
    @pytest.mark.asyncio
    async def test_message_visibility_timeout_extension(self, sqs_tool):
        """Test extending message visibility timeout"""
        with patch('boto3.client') as mock_boto_client:
            mock_sqs = MagicMock()
            mock_boto_client.return_value = mock_sqs
            mock_sqs.change_message_visibility.return_value = {}
            
            receipt_handle = "test-receipt-handle"
            visibility_timeout = 600  # 10 minutes
            
            result = await sqs_tool.extend_message_visibility(receipt_handle, visibility_timeout)
            
            assert result["success"] is True
            
            # Verify change_message_visibility was called correctly
            mock_sqs.change_message_visibility.assert_called_once_with(
                QueueUrl=sqs_tool.queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout
            )