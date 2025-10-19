"""""Test configuration for remediation agent tests."""

import pytest
import asyncio
from typing import Generator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

# Import remediation agent components
from src.remediation_agent.state.models import (
    RemediationSignal,
    RemediationDecision,
    RemediationType,
    WorkflowStatus,
    WorkflowType,
    RemediationWorkflow,
    WorkflowStep,
    RemediationMetrics,
    HumanTask,
    SignalType,
    UrgencyLevel
)
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation,
    DataProcessingActivity,
    RiskLevel,
    DataType,
    ComplianceFramework
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==========================================
# TEST DATA FIXTURES
# ==========================================

@pytest.fixture
def sample_compliance_violation() -> ComplianceViolation:
    """Create a sample compliance violation for testing"""
    return ComplianceViolation(
        rule_id="gdpr_art17_violation_001",
        activity_id="user_data_001",
        description="User requested data deletion but system lacks automated deletion capability",
        risk_level=RiskLevel.HIGH,
        remediation_actions=[
            "Delete user personal data from database",
            "Remove user from mailing lists",
            "Verify complete data removal",
            "Send confirmation to user"
        ]
    )


@pytest.fixture
def sample_data_processing_activity() -> DataProcessingActivity:
    """Create a sample data processing activity for testing"""
    return DataProcessingActivity(
        id="user_data_001",
        name="User Profile Management",
        purpose="Account management and personalization",
        data_types=[DataType.PERSONAL_DATA, DataType.BEHAVIORAL_DATA],
        legal_bases=["consent"],
        recipients=["internal_systems"],
        retention_period=1825,  # 5 years in days
        security_measures=["encryption", "access_controls"]
    )


@pytest.fixture
def sample_remediation_signal(sample_compliance_violation, sample_data_processing_activity) -> RemediationSignal:
    """Create a sample remediation signal for testing"""
    return RemediationSignal(
        signal_id=str(uuid4()),
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        signal_type=SignalType.COMPLIANCE_VIOLATION,
        confidence_score=0.9,
        urgency_level=UrgencyLevel.HIGH,
        detected_violations=["gdpr_art17_violation"],
        recommended_actions=["delete_user_data"],
        context={
            "user_request_id": "user_123",
            "request_timestamp": datetime.now(timezone.utc).isoformat(),
            "affected_systems": ["user_db", "analytics_db", "email_service"]
        },
        id=str(uuid4()),
        priority=RiskLevel.HIGH,
        violation=sample_compliance_violation,
        activity=sample_data_processing_activity
    )


@pytest.fixture
def sample_remediation_decision() -> RemediationDecision:
    """Create a sample remediation decision for testing"""
    return RemediationDecision(
        violation_id="violation_123",
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        confidence_score=0.85,
        reasoning="High-risk operation requires human oversight for data deletion",
        estimated_effort=60,
        risk_if_delayed=RiskLevel.HIGH,
        prerequisites=["data_protection_officer_approval"]
    )


@pytest.fixture
def sample_workflow_step() -> WorkflowStep:
    """Create a sample workflow step for testing"""
    return WorkflowStep(
        id=str(uuid4()),
        name="Delete User Data",
        description="Remove all personal data for user from database",
        action_type="data_deletion",
        parameters={
            "user_id": "user_123",
            "tables": ["users", "user_preferences", "user_history"],
            "verify_deletion": True
        },
        estimated_duration_minutes=15
    )


@pytest.fixture
def sample_remediation_workflow(sample_workflow_step) -> RemediationWorkflow:
    """Create a sample remediation workflow for testing"""
    return RemediationWorkflow(
        id=str(uuid4()),
        violation_id="violation_123",
        activity_id="user_data_001",
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        workflow_type=WorkflowType.HUMAN_IN_LOOP,
        status=WorkflowStatus.PENDING,
        steps=[sample_workflow_step],
        metadata={
            "framework": "gdpr_eu",
            "priority": "high",
            "requester": "user_123"
        }
    )


@pytest.fixture
def sample_human_task() -> HumanTask:
    """Create a sample human task for testing"""
    return HumanTask(
        id=str(uuid4()),
        workflow_id="workflow_123",
        title="Approve Data Deletion",
        description="Review and approve deletion of user personal data",
        assignee="data_protection_officer",
        priority=RiskLevel.HIGH,
        due_date=datetime.now(timezone.utc).replace(hour=23, minute=59)
    )


@pytest.fixture
def sample_remediation_metrics() -> RemediationMetrics:
    """Create sample remediation metrics for testing"""
    return RemediationMetrics(
        total_violations_processed=100,
        automatic_remediations=45,
        human_loop_remediations=35,
        manual_remediations=20,
        success_rate=0.85,
        average_resolution_time=120.5,
        by_risk_level={RiskLevel.HIGH: 30, RiskLevel.MEDIUM: 50, RiskLevel.LOW: 20},
        by_framework={"gdpr_eu": 60, "ccpa_california": 25, "pdpa_singapore": 15}
    )


# ==========================================
# MOCK FIXTURES
# ==========================================

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for decision agent testing"""
    return {
        "remediation_type": "human_in_loop",
        "confidence_score": 0.85,
        "reasoning": "High-risk data deletion requires human oversight",
        "estimated_effort": "medium",
        "automation_potential": 0.7,
        "risk_assessment": {
            "data_risk": "high",
            "system_risk": "medium",
            "compliance_risk": "low"
        },
        "required_approvals": ["data_protection_officer"],
        "human_tasks": [
            "Review deletion scope",
            "Approve data removal",
            "Verify compliance"
        ]
    }


@pytest.fixture
def mock_chat_openai():
    """Mock ChatOpenAI for testing"""
    mock = AsyncMock()
    mock.ainvoke.return_value = MagicMock()
    mock.ainvoke.return_value.content = '{"remediation_type": "human_in_loop", "confidence_score": 0.85}'
    return mock


@pytest.fixture
def mock_sqs_tool():
    """Mock SQS tool for testing"""
    mock = AsyncMock()
    mock.send_message.return_value = {"MessageId": "msg_123", "success": True}
    mock.receive_messages.return_value = []
    return mock


@pytest.fixture
def mock_notification_tool():
    """Mock notification tool for testing"""
    mock = AsyncMock()
    mock.send_notification.return_value = {"success": True, "notification_id": "notif_123"}
    return mock


@pytest.fixture
def mock_remediation_validator():
    """Mock remediation validator for testing"""
    mock = AsyncMock()
    mock.validate_remediation_action.return_value = {
        "valid": True,
        "confidence": 0.9,
        "issues": [],
        "recommendations": []
    }
    return mock


@pytest.fixture
def mock_database_connection():
    """Mock database connection for testing"""
    mock = AsyncMock()
    mock.execute.return_value = {"affected_rows": 1, "success": True}
    mock.fetch_all.return_value = []
    return mock


# ==========================================
# AGENT FIXTURES
# ==========================================

@pytest.fixture
def mock_decision_agent():
    """Mock decision agent for testing"""
    from src.remediation_agent.agents.decision_agent import DecisionAgent
    
    with patch.object(DecisionAgent, '__init__', return_value=None):
        agent = DecisionAgent.__new__(DecisionAgent)
        agent.llm = AsyncMock()
        agent.prompt = MagicMock()
        agent.analyze_violation = AsyncMock()
        yield agent


@pytest.fixture
def mock_validation_agent():
    """Mock validation agent for testing"""
    from src.remediation_agent.agents.validation_agent import ValidationAgent
    
    with patch.object(ValidationAgent, '__init__', return_value=None):
        agent = ValidationAgent.__new__(ValidationAgent)
        agent.assess_feasibility = AsyncMock()
        yield agent


@pytest.fixture
def mock_workflow_agent():
    """Mock workflow agent for testing"""
    from src.remediation_agent.agents.workflow_agent import WorkflowAgent
    
    with patch.object(WorkflowAgent, '__init__', return_value=None):
        agent = WorkflowAgent.__new__(WorkflowAgent)
        agent.create_workflow = AsyncMock()
        agent.execute_workflow = AsyncMock()
        yield agent


# ==========================================
# ENVIRONMENT FIXTURES
# ==========================================

@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing"""
    env_vars = {
        "OPENAI_API_KEY": "test_api_key",
        "AWS_ACCESS_KEY_ID": "test_access_key",
        "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        "AWS_REGION": "us-east-1",
        "REMEDIATION_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789/remediation-queue",
        "NOTIFICATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789:remediation-notifications"
    }

    # Also mock the Secrets Manager to return the test API key
    with patch.dict('os.environ', env_vars):
        with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key', return_value="test_api_key"):
            yield env_vars


@pytest.fixture
def mock_secrets_manager():
    """Mock AWS Secrets Manager for testing"""
    with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock:
        mock.return_value = "test_api_key_from_secrets"
        yield mock


@pytest.fixture
def mock_secrets_manager_unavailable():
    """Mock AWS Secrets Manager being unavailable"""
    with patch('src.compliance_agent.services.ai_secrets_service.get_openai_api_key') as mock:
        mock.return_value = None
        yield mock


# ==========================================
# UTILITY FIXTURES
# ==========================================

@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing"""
    fixed_time = datetime(2025, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    with patch('src.remediation_agent.state.models.utc_now', return_value=fixed_time):
        yield fixed_time


@pytest.fixture
def sample_workflow_steps(sample_workflow_step) -> List[WorkflowStep]:
    """Create multiple sample workflow steps for testing"""
    steps = [sample_workflow_step]
    # Create a second step
    from uuid import uuid4
    step2 = WorkflowStep(
        id=str(uuid4()),
        name="Send Notification",
        description="Notify user of data deletion",
        action_type="notification",
        parameters={
            "email": "user@example.com",
            "template": "data_deletion_notice"
        }
    )
    steps.append(step2)
    return steps

@pytest.fixture
def mock_uuid():
    """Mock UUID generator for consistent testing"""
    test_uuid = "test-uuid-123"
    with patch('uuid.uuid4') as mock_uuid4:
        mock_uuid4.return_value.hex = test_uuid
        with patch('str', return_value=test_uuid):
            yield test_uuid

@pytest.fixture
def sample_automatic_decision(
    sample_compliance_violation: ComplianceViolation,
    sample_data_processing_activity: DataProcessingActivity,
) -> RemediationDecision:
    return RemediationDecision(
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        remediation_type=RemediationType.AUTOMATIC,
        confidence_score=0.9,
        reasoning="Simple data preference update with high confidence",
        estimated_effort=15,
        risk_if_delayed=RiskLevel.LOW,
    )


@pytest.fixture
def sample_human_in_loop_decision(
    sample_compliance_violation: ComplianceViolation,
    sample_data_processing_activity: DataProcessingActivity,
) -> RemediationDecision:
    return RemediationDecision(
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        remediation_type=RemediationType.HUMAN_IN_LOOP,
        confidence_score=0.75,
        reasoning="Data deletion requires human oversight",
        estimated_effort=60,
        risk_if_delayed=RiskLevel.MEDIUM,
        prerequisites=["dpo_approval"],
    )


@pytest.fixture
def sample_manual_decision(
    sample_compliance_violation: ComplianceViolation,
    sample_data_processing_activity: DataProcessingActivity,
) -> RemediationDecision:
    return RemediationDecision(
        violation_id=sample_compliance_violation.rule_id,
        activity_id=sample_data_processing_activity.id,
        remediation_type=RemediationType.MANUAL_ONLY,
        confidence_score=0.6,
        reasoning="Complex legal changes require manual implementation",
        estimated_effort=480,
        risk_if_delayed=RiskLevel.CRITICAL,
        prerequisites=["legal_review", "executive_signoff"],
    )


@pytest.fixture
def sample_violation(
    sample_compliance_violation: ComplianceViolation,
) -> ComplianceViolation:
    """Mirror of the workflow test violation fixture."""

    return ComplianceViolation(
        id=sample_compliance_violation.rule_id,
        violation_type="unauthorized_data_processing",
        description=sample_compliance_violation.description,
        risk_level=sample_compliance_violation.risk_level,
        framework=ComplianceFramework.GDPR_EU,
        data_subject_id="user-456",
        affected_data_types=[DataType.PERSONAL_DATA],
        remediation_actions=sample_compliance_violation.remediation_actions,
        evidence={"log_entry": "Unauthorized access detected"},
        detection_timestamp="2024-01-15T10:30:00Z",
    )
