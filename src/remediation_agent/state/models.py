"""
Pydantic models for remediation agent state management
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from src.compliance_agent.models.compliance_models import (
    RiskLevel, ComplianceViolation, DataProcessingActivity
)


def utc_now() -> datetime:
    """Helper function to get current UTC time"""
    return datetime.now(timezone.utc)


class ValidationStatus(str, Enum):
    """Status of validation result"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class ValidationResult(BaseModel):
    """Result of validation operation"""
    status: ValidationStatus = Field(..., description="Validation status")
    confidence_score: float = Field(..., description="Confidence in validation")
    validation_errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    recommendations: List[str] = Field(default_factory=list, description="List of recommendations")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional validation details")


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


class SignalType(str, Enum):
    """Types of remediation signals"""
    COMPLIANCE_VIOLATION = "compliance_violation"
    POLICY_BREACH = "policy_breach"
    DATA_RISK = "data_risk"
    REGULATORY_CHANGE = "regulatory_change"


class UrgencyLevel(str, Enum):
    """Urgency levels for remediation actions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationDecision(BaseModel):
    """Represents a decision on how to remediate a compliance violation."""
    
    violation_id: str = Field(..., description="ID of the related compliance violation")
    remediation_type: RemediationType = Field(
        ..., description="Type of remediation approach"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the decision"
    )
    reasoning: str = Field(..., description="Explanation of the decision logic")
    estimated_effort: int = Field(
        ..., gt=0, description="Estimated effort in minutes"
    )
    risk_if_delayed: RiskLevel = Field(
        ..., description="Risk level if remediation is delayed"
    )
    prerequisites: List[str] = Field(
        default=[], description="Prerequisites before remediation can start"
    )


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
    estimated_duration_minutes: int = Field(default=5, gt=0, description="Estimated duration in minutes")
    created_at: datetime = Field(default_factory=utc_now, description="Step creation timestamp")
    order: int = Field(default=0, description="Step execution order")
    
    # Compatibility field for tests
    @property
    def action(self) -> str:
        """Compatibility property that returns action_type"""
        return self.action_type


class RemediationWorkflow(BaseModel):
    """Represents a workflow for executing remediation actions."""
    
    id: str = Field(..., description="Unique identifier for the workflow")
    violation_id: str = Field(..., description="ID of the related compliance violation")
    activity_id: str = Field(..., description="ID of the related activity")
    remediation_type: RemediationType = Field(
        ..., description="Type of remediation approach"
    )
    workflow_type: WorkflowType = Field(
        ..., description="Type of workflow execution"
    )
    status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING, description="Current workflow status"
    )
    steps: List[WorkflowStep] = Field(
        default=[], description="Ordered list of workflow steps"
    )
    current_step_index: int = Field(
        default=0, ge=0, description="Index of the currently executing step"
    )
    metadata: Dict[str, Any] = Field(
        default={}, description="Additional workflow metadata"
    )
    priority: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Priority level of the workflow"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="When the workflow was created"
    )


class RemediationSignal(BaseModel):
    """Represents a signal indicating need for remediation action."""
    
    signal_id: str = Field(..., description="Unique identifier for the signal")
    violation_id: str = Field(
        ..., description="ID of the compliance violation"
    )
    activity_id: str = Field(..., description="ID of the related activity")
    signal_type: SignalType = Field(
        ..., description="Type of remediation signal"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the signal"
    )
    urgency_level: UrgencyLevel = Field(
        ..., description="How urgent the remediation is"
    )
    detected_violations: List[str] = Field(
        default=[], description="List of detected violations"
    )
    recommended_actions: List[str] = Field(
        default=[], description="Recommended remediation actions"
    )
    context: Dict[str, Any] = Field(
        default={}, description="Additional context for the signal"
    )
    id: str = Field(..., description="Unique identifier")
    priority: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Priority level")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the signal was created"
    )
    
    # Optional relationship fields for testing
    violation: Optional[ComplianceViolation] = Field(
        default=None, description="The related compliance violation object"
    )
    activity: Optional[DataProcessingActivity] = Field(
        default=None, description="The related data processing activity object"
    )


class HumanTask(BaseModel):
    """Represents a task that requires human intervention."""
    
    id: str = Field(..., description="Unique identifier for the task")
    workflow_id: str = Field(..., description="ID of the related workflow")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    assignee: str = Field(..., description="Person or role assigned to the task")
    priority: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Task priority level"
    )
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Current task status")
    instructions: List[str] = Field(
        default=[], description="List of instructions for completing the task"
    )
    required_approvals: List[str] = Field(
        default=[], description="List of required approvals for this task"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the task was created"
    )
    due_date: Optional[datetime] = Field(
        None, description="When the task is due"
    )
    completed_at: Optional[datetime] = Field(
        None, description="When the task was completed"
    )
    completed_by: Optional[str] = Field(
        None, description="Who completed the task"
    )


class RemediationMetrics(BaseModel):
    """Model for tracking remediation metrics"""
    total_violations_processed: int = Field(default=0, ge=0, description="Total violations processed")
    automatic_remediations: int = Field(default=0, ge=0, description="Number of automatic remediations") 
    human_loop_remediations: int = Field(default=0, ge=0, description="Number of human-in-loop remediations")
    manual_remediations: int = Field(default=0, ge=0, description="Number of manual remediations")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall success rate")
    average_resolution_time: float = Field(default=0.0, ge=0.0, description="Average resolution time in minutes")
    by_risk_level: Dict[RiskLevel, int] = Field(default_factory=dict, description="Breakdown by risk level")
    by_framework: Dict[str, int] = Field(default_factory=dict, description="Breakdown by framework")