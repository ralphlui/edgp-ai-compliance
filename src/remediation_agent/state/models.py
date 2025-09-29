"""
Pydantic models for remediation agent state management
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from compliance_agent.models.compliance_models import (
    ComplianceViolation,
    RiskLevel,
    DataProcessingActivity
)


def utc_now() -> datetime:
    """Helper function to get current UTC time"""
    return datetime.now(timezone.utc)


class RemediationType(str, Enum):
    """Types of remediation approaches"""
    AUTOMATIC = "automatic"
    HUMAN_IN_LOOP = "human_in_loop"
    MANUAL_ONLY = "manual_only"


class WorkflowStatus(str, Enum):
    """Status of remediation workflows"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_HUMAN = "requires_human"


class WorkflowType(str, Enum):
    """Type of remediation workflow"""
    AUTOMATIC = "automatic"
    HUMAN_IN_LOOP = "human_in_loop"
    MANUAL_ONLY = "manual_only"


class RemediationDecision(BaseModel):
    """Model for remediation decision"""
    violation_id: str = Field(..., description="ID of the compliance violation")
    remediation_type: RemediationType = Field(..., description="Type of remediation approach")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the decision")
    reasoning: str = Field(..., description="Explanation for the decision")
    estimated_effort: int = Field(..., description="Estimated effort in minutes")
    risk_if_delayed: RiskLevel = Field(..., description="Risk if remediation is delayed")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites for remediation")


class WorkflowStep(BaseModel):
    """Model for individual workflow steps"""
    id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="Step description")
    action_type: str = Field(..., description="Type of action (api_call, data_update, notification)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Step status")
    error_message: Optional[str] = Field(None, description="Error message if step failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class RemediationWorkflow(BaseModel):
    """Model for remediation workflow"""
    id: str = Field(..., description="Unique workflow identifier")
    violation_id: str = Field(..., description="Associated compliance violation ID")
    activity_id: str = Field(..., description="Associated data processing activity ID")
    remediation_type: RemediationType = Field(..., description="Type of remediation")
    workflow_type: WorkflowType = Field(..., description="Type of workflow (automatic, human_in_loop, manual_only)")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Workflow status")
    steps: List[WorkflowStep] = Field(default_factory=list, description="Workflow steps")
    sqs_queue_url: Optional[str] = Field(None, description="AWS SQS queue URL for the workflow")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    human_assignee: Optional[str] = Field(None, description="Human assignee for manual steps")
    priority: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Workflow priority")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RemediationSignal(BaseModel):
    """Model for incoming remediation signals from compliance agent"""
    violation: ComplianceViolation = Field(..., description="Compliance violation to remediate")
    activity: DataProcessingActivity = Field(..., description="Associated data processing activity")
    framework: str = Field(..., description="Compliance framework")
    urgency: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Urgency of remediation")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    received_at: datetime = Field(default_factory=utc_now, description="Signal received timestamp")


class HumanTask(BaseModel):
    """Model for human tasks in remediation workflows"""
    id: str = Field(..., description="Unique task identifier")
    workflow_id: str = Field(..., description="Associated workflow ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    assignee: str = Field(..., description="Human assignee")
    priority: RiskLevel = Field(..., description="Task priority")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Task status")
    instructions: List[str] = Field(default_factory=list, description="Detailed instructions")
    required_approvals: List[str] = Field(default_factory=list, description="Required approvals")


class RemediationMetrics(BaseModel):
    """Model for tracking remediation metrics"""
    total_violations_processed: int = Field(default=0, description="Total violations processed")
    automatic_remediations: int = Field(default=0, description="Number of automatic remediations")
    human_loop_remediations: int = Field(default=0, description="Number of human-in-loop remediations")
    manual_remediations: int = Field(default=0, description="Number of manual remediations")
    success_rate: float = Field(default=0.0, description="Overall success rate")
    average_resolution_time: float = Field(default=0.0, description="Average resolution time in minutes")
    by_risk_level: Dict[RiskLevel, int] = Field(default_factory=dict, description="Breakdown by risk level")
    by_framework: Dict[str, int] = Field(default_factory=dict, description="Breakdown by framework")