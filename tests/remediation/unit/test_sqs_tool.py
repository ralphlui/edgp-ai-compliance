"""
Unit tests for SQSTool - Clean implementation

Tests focus on methods that exist. TODO markers indicate future work.
"""

import pytest
from datetime import datetime, timezone
from src.remediation_agent.tools.sqs_tool import SQSTool
from src.remediation_agent.state.models import RemediationSignal, SignalType


class TestSQSToolBasics:
    """Test SQSTool initialization and configuration"""

    def test_sqs_tool_creation(self):
        """Test that SQS tool can be created"""
        tool = SQSTool()
        assert tool is not None
        assert isinstance(tool, SQSTool)

    def test_sqs_tool_has_queue_urls_dict(self):
        """Test that queue_urls dictionary is initialized"""
        tool = SQSTool()
        assert hasattr(tool, 'queue_urls')
        assert isinstance(tool.queue_urls, dict)

    def test_get_all_configured_queues(self):
        """Test retrieving all configured queue URLs"""
        tool = SQSTool()
        queues = tool.get_all_configured_queues()
        assert isinstance(queues, dict)
        assert 'main_queue' in queues

    def test_serialize_signal(self):
        """Test signal serialization"""
        tool = SQSTool()
        signal = RemediationSignal(
            signal_id="sig-001",
            violation_id="v-001",
            activity_id="a-001",
            signal_type=SignalType.COMPLIANCE_VIOLATION,
            timestamp=datetime.now(timezone.utc),
            severity="high",
            description="Test"
        )
        result = tool.serialize_remediation_signal(signal)
        assert isinstance(result, str)
        assert "sig-001" in result
