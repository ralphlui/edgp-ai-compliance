"""
AWS SQS Tool for remediation workflow queue management

This tool provides functionality to create and manage AWS SQS queues
for remediation workflows.
"""

import boto3
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from botocore.exceptions import ClientError, BotoCoreError

# Import settings - handle import gracefully
try:
    from config.settings import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    settings = None

logger = logging.getLogger(__name__)


class SQSTool:
    """
    Tool for managing AWS SQS queues for remediation workflows
    """

    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize SQS tool

        Args:
            region_name: AWS region for SQS operations (defaults to AWS_REGION env var or us-east-1)
        """
        # Set region from settings, parameter, or environment
        if SETTINGS_AVAILABLE and settings and settings.aws_region:
            self.region_name = settings.aws_region
        else:
            self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.sqs_client = None

        # Load environment configuration
        self.config = self._load_sqs_config()

        self._initialize_client()

    def _load_sqs_config(self) -> Dict[str, Any]:
        """Load SQS configuration from settings or environment variables"""
        if SETTINGS_AVAILABLE and settings:
            # Use pydantic settings first
            return {
                "main_queue_url": settings.sqs_main_queue_url,
                "dlq_url": settings.sqs_dlq_url,
                "high_priority_queue_url": settings.sqs_high_priority_queue_url,
                "human_intervention_queue_url": settings.sqs_human_intervention_queue_url,
                "message_retention_period": str(settings.sqs_message_retention_period),
                "visibility_timeout": str(settings.sqs_visibility_timeout),
                "receive_message_wait_time": str(settings.sqs_receive_message_wait_time),
                "max_receive_count": str(settings.sqs_max_receive_count)
            }
        else:
            # Fallback to environment variables
            return {
                "main_queue_url": os.getenv("SQS_MAIN_QUEUE_URL"),
                "dlq_url": os.getenv("SQS_DLQ_URL"),
                "high_priority_queue_url": os.getenv("SQS_HIGH_PRIORITY_QUEUE_URL"),
                "human_intervention_queue_url": os.getenv("SQS_HUMAN_INTERVENTION_QUEUE_URL"),
                "message_retention_period": os.getenv("SQS_MESSAGE_RETENTION_PERIOD", "1209600"),
                "visibility_timeout": os.getenv("SQS_VISIBILITY_TIMEOUT", "300"),
                "receive_message_wait_time": os.getenv("SQS_RECEIVE_MESSAGE_WAIT_TIME", "20"),
                "max_receive_count": os.getenv("SQS_MAX_RECEIVE_COUNT", "3")
            }

    def _initialize_client(self):
        """Initialize AWS SQS client"""
        try:
            self.sqs_client = boto3.client('sqs', region_name=self.region_name)
            logger.info(f"SQS client initialized for region {self.region_name}")
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {str(e)}")
            # In development/testing, we might not have AWS credentials
            self.sqs_client = None

    async def create_remediation_queue(
        self,
        queue_name: str,
        workflow_id: str,
        attributes: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create an SQS queue for a remediation workflow

        Args:
            queue_name: Name of the queue to create
            workflow_id: ID of the associated workflow
            attributes: Additional queue attributes

        Returns:
            Dictionary containing queue URL and metadata
        """
        logger.info(f"Creating SQS queue {queue_name} for workflow {workflow_id}")

        if not self.sqs_client:
            # Fallback for development/testing without AWS credentials
            return self._create_mock_queue(queue_name, workflow_id)

        try:
            # Default queue attributes for remediation workflows
            default_attributes = {
                'DelaySeconds': '0',
                'MaxReceiveCount': '3',
                'MessageRetentionPeriod': '1209600',  # 14 days
                'VisibilityTimeoutSeconds': '300',     # 5 minutes
                'ReceiveMessageWaitTimeSeconds': '10'   # Long polling
            }

            # Merge with custom attributes
            if attributes:
                default_attributes.update(attributes)

            # Create the queue
            response = self.sqs_client.create_queue(
                QueueName=queue_name,
                Attributes=default_attributes,
                tags={
                    'WorkflowId': workflow_id,
                    'Purpose': 'RemediationWorkflow',
                    'CreatedAt': datetime.now(timezone.utc).isoformat(),
                    'ManagedBy': 'RemediationAgent'
                }
            )

            queue_url = response['QueueUrl']

            # Create dead letter queue for failed messages
            dlq_response = await self._create_dead_letter_queue(queue_name, workflow_id)

            # Configure dead letter queue redrive policy
            if dlq_response['success']:
                await self._configure_dead_letter_queue(queue_url, dlq_response['queue_arn'])

            logger.info(f"SQS queue created successfully: {queue_url}")

            return {
                'success': True,
                'queue_url': queue_url,
                'queue_name': queue_name,
                'dead_letter_queue': dlq_response.get('queue_url'),
                'attributes': default_attributes,
                'workflow_id': workflow_id,
                'created_at': datetime.now(timezone.utc).isoformat()
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'QueueAlreadyExists':
                # Queue already exists, get its URL
                try:
                    response = self.sqs_client.get_queue_url(QueueName=queue_name)
                    logger.info(f"Queue {queue_name} already exists: {response['QueueUrl']}")
                    return {
                        'success': True,
                        'queue_url': response['QueueUrl'],
                        'queue_name': queue_name,
                        'workflow_id': workflow_id,
                        'already_existed': True
                    }
                except ClientError:
                    pass

            logger.error(f"Failed to create SQS queue {queue_name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': error_code
            }

        except Exception as e:
            logger.error(f"Unexpected error creating SQS queue: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

    async def _create_dead_letter_queue(
        self,
        main_queue_name: str,
        workflow_id: str
    ) -> Dict[str, Any]:
        """Create a dead letter queue for failed messages"""
        dlq_name = f"{main_queue_name}-dlq"

        try:
            dlq_attributes = {
                'MessageRetentionPeriod': '1209600',  # 14 days
                'VisibilityTimeoutSeconds': '300'
            }

            response = self.sqs_client.create_queue(
                QueueName=dlq_name,
                Attributes=dlq_attributes,
                tags={
                    'WorkflowId': workflow_id,
                    'Purpose': 'DeadLetterQueue',
                    'ParentQueue': main_queue_name,
                    'CreatedAt': datetime.now(timezone.utc).isoformat()
                }
            )

            # Get queue ARN
            queue_url = response['QueueUrl']
            queue_arn = await self._get_queue_arn(queue_url)

            return {
                'success': True,
                'queue_url': queue_url,
                'queue_arn': queue_arn,
                'queue_name': dlq_name
            }

        except Exception as e:
            logger.error(f"Failed to create dead letter queue: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _get_queue_arn(self, queue_url: str) -> str:
        """Get the ARN of a queue"""
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )
            return response['Attributes']['QueueArn']
        except Exception as e:
            logger.error(f"Failed to get queue ARN: {str(e)}")
            return ""

    async def _configure_dead_letter_queue(
        self,
        main_queue_url: str,
        dlq_arn: str,
        max_receive_count: int = 3
    ):
        """Configure dead letter queue redrive policy"""
        try:
            redrive_policy = {
                'deadLetterTargetArn': dlq_arn,
                'maxReceiveCount': max_receive_count
            }

            self.sqs_client.set_queue_attributes(
                QueueUrl=main_queue_url,
                Attributes={
                    'RedrivePolicy': json.dumps(redrive_policy)
                }
            )

            logger.info(f"Dead letter queue configured for {main_queue_url}")

        except Exception as e:
            logger.error(f"Failed to configure dead letter queue: {str(e)}")

    async def send_workflow_message(
        self,
        queue_url: str,
        message_body: Dict[str, Any],
        delay_seconds: int = 0
    ) -> Dict[str, Any]:
        """
        Send a message to a remediation workflow queue

        Args:
            queue_url: URL of the SQS queue
            message_body: Message content
            delay_seconds: Delay before message becomes available

        Returns:
            Send message response
        """
        logger.info(f"📡 [SQS-SEND-START] Sending workflow message to SQS")
        logger.info(f"🔗 [SQS-QUEUE] Queue URL: {queue_url}")
        logger.info(f"📋 [MESSAGE-BODY] Keys: {list(message_body.keys())}")
        logger.info(f"⏰ [DELAY] Delay seconds: {delay_seconds}")

        if not self.sqs_client:
            logger.info(f"🔄 [SQS-MOCK-MODE] No SQS client available, using mock message sender")
            return self._send_mock_message(queue_url, message_body)

        try:
            # Add metadata to message
            logger.info(f"📝 [MESSAGE-ENHANCE] Adding metadata to message body")
            enhanced_message = {
                **message_body,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'remediation_agent',
                'version': '1.0'
            }
            logger.info(f"✅ [MESSAGE-ENHANCED] Enhanced message keys: {list(enhanced_message.keys())}")

            message_type = message_body.get('type', 'workflow_step')
            workflow_id = message_body.get('workflow_id', 'unknown')
            logger.info(f"🏷️ [MESSAGE-ATTRS] Type: {message_type}, Workflow: {workflow_id}")

            logger.info(f"📡 [SQS-SEND] Sending message to SQS queue")
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(enhanced_message),
                DelaySeconds=delay_seconds,
                MessageAttributes={
                    'MessageType': {
                        'StringValue': message_type,
                        'DataType': 'String'
                    },
                    'WorkflowId': {
                        'StringValue': workflow_id,
                        'DataType': 'String'
                    },
                    'Priority': {
                        'StringValue': message_body.get('priority', 'medium'),
                        'DataType': 'String'
                    }
                }
            )

            message_id = response.get('MessageId', 'unknown')
            md5_hash = response.get('MD5OfBody', 'unavailable')
            logger.info(f"✅ [SQS-SEND-SUCCESS] Message sent successfully to SQS queue")
            logger.info(f"🆔 [MESSAGE-ID] {message_id}")
            logger.info(f"🔐 [MD5-HASH] {md5_hash}")

            result = {
                'success': True,
                'message_id': message_id,
                'md5_of_body': md5_hash,
                'queue_url': queue_url
            }
            logger.info(f"📤 [SQS-RESPONSE] Returning success response with message details")
            return result

        except Exception as e:
            logger.error(f"❌ [SQS-SEND-FAILED] Failed to send message to queue {queue_url}: {str(e)}")
            logger.error(f"📊 [ERROR-TYPE] Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"🔍 [ERROR-TRACEBACK] {traceback.format_exc()}")

            error_result = {
                'success': False,
                'error': str(e)
            }
            logger.info(f"📤 [SQS-ERROR-RESPONSE] Returning error response")
            return error_result

    async def receive_workflow_messages(
        self,
        queue_url: str,
        max_messages: int = 1,
        wait_time_seconds: int = 10
    ) -> Dict[str, Any]:
        """
        Receive messages from a remediation workflow queue

        Args:
            queue_url: URL of the SQS queue
            max_messages: Maximum number of messages to receive
            wait_time_seconds: Long polling wait time

        Returns:
            Received messages
        """
        if not self.sqs_client:
            return self._receive_mock_messages(queue_url, max_messages)

        try:
            response = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])

            # Parse message bodies
            parsed_messages = []
            for message in messages:
                try:
                    body = json.loads(message['Body'])
                    parsed_messages.append({
                        'message_id': message['MessageId'],
                        'receipt_handle': message['ReceiptHandle'],
                        'body': body,
                        'attributes': message.get('MessageAttributes', {}),
                        'md5_of_body': message['MD5OfBody']
                    })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message body: {message['Body']}")
                    parsed_messages.append({
                        'message_id': message['MessageId'],
                        'receipt_handle': message['ReceiptHandle'],
                        'body': message['Body'],
                        'attributes': message.get('MessageAttributes', {}),
                        'parse_error': True
                    })

            return {
                'success': True,
                'messages': parsed_messages,
                'message_count': len(parsed_messages)
            }

        except Exception as e:
            logger.error(f"Failed to receive messages from queue {queue_url}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'messages': []
            }

    async def delete_message(
        self,
        queue_url: str,
        receipt_handle: str
    ) -> Dict[str, Any]:
        """Delete a processed message from the queue"""
        if not self.sqs_client:
            return {'success': True, 'mock': True}

        try:
            self.sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )

            return {'success': True}

        except Exception as e:
            logger.error(f"Failed to delete message: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """Get queue attributes and statistics"""
        if not self.sqs_client:
            return self._get_mock_queue_attributes(queue_url)

        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )

            attributes = response['Attributes']

            return {
                'success': True,
                'queue_url': queue_url,
                'attributes': attributes,
                'message_count': int(attributes.get('ApproximateNumberOfMessages', 0)),
                'messages_in_flight': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0)),
                'created_timestamp': attributes.get('CreatedTimestamp'),
                'last_modified_timestamp': attributes.get('LastModifiedTimestamp')
            }

        except Exception as e:
            logger.error(f"Failed to get queue attributes: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_mock_queue(self, queue_name: str, workflow_id: str) -> Dict[str, Any]:
        """Create a mock queue for development/testing"""
        mock_url = f"https://sqs.mock-region.amazonaws.com/123456789012/{queue_name}"

        logger.info(f"Created mock SQS queue: {mock_url}")

        return {
            'success': True,
            'queue_url': mock_url,
            'queue_name': queue_name,
            'workflow_id': workflow_id,
            'mock': True,
            'created_at': datetime.now(timezone.utc).isoformat()
        }

    def _send_mock_message(self, queue_url: str, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """Send a mock message for development/testing"""
        import uuid

        mock_message_id = str(uuid.uuid4())
        logger.info(f"🎭 [SQS-MOCK-SEND] Sending mock message for development/testing")
        logger.info(f"🔗 [MOCK-QUEUE] Queue URL: {queue_url}")
        logger.info(f"📋 [MOCK-MESSAGE] Keys: {list(message_body.keys())}")
        logger.info(f"🆔 [MOCK-MESSAGE-ID] {mock_message_id}")

        result = {
            'success': True,
            'message_id': mock_message_id,
            'md5_of_body': 'mock_md5_hash',
            'queue_url': queue_url,
            'mock': True
        }
        logger.info(f"✅ [SQS-MOCK-SUCCESS] Mock message sent successfully")
        return result

    def _receive_mock_messages(self, queue_url: str, max_messages: int) -> Dict[str, Any]:
        """Receive mock messages for development/testing"""
        return {
            'success': True,
            'messages': [],
            'message_count': 0,
            'mock': True
        }

    def _get_mock_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """Get mock queue attributes for development/testing"""
        return {
            'success': True,
            'queue_url': queue_url,
            'attributes': {
                'ApproximateNumberOfMessages': '0',
                'ApproximateNumberOfMessagesNotVisible': '0',
                'CreatedTimestamp': str(int(datetime.now(timezone.utc).timestamp())),
                'LastModifiedTimestamp': str(int(datetime.now(timezone.utc).timestamp()))
            },
            'message_count': 0,
            'messages_in_flight': 0,
            'mock': True
        }

    def get_queue_url_for_type(self, remediation_type: str) -> Optional[str]:
        """
        Get the appropriate queue URL for a remediation type

        Args:
            remediation_type: Type of remediation (automatic, human_in_loop, manual_only)

        Returns:
            Queue URL for the remediation type, or None if not configured
        """
        queue_mapping = {
            'automatic': self.config.get('main_queue_url'),
            'human_in_loop': self.config.get('human_intervention_queue_url'),
            'manual_only': self.config.get('human_intervention_queue_url'),
            'high_priority': self.config.get('high_priority_queue_url')
        }

        return queue_mapping.get(remediation_type.lower())

    def get_all_configured_queues(self) -> Dict[str, Optional[str]]:
        """Get all configured queue URLs from environment"""
        return {
            'main_queue': self.config.get('main_queue_url'),
            'dlq': self.config.get('dlq_url'),
            'high_priority_queue': self.config.get('high_priority_queue_url'),
            'human_intervention_queue': self.config.get('human_intervention_queue_url')
        }

    def is_configured(self) -> bool:
        """Check if SQS queues are properly configured in environment"""
        required_queues = ['main_queue_url', 'dlq_url', 'human_intervention_queue_url']
        return all(self.config.get(queue) for queue in required_queues)