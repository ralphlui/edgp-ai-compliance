"""
Pydantic models for remediation agent state management
"""


from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

from pydantic import BaseModel, Field, model_validator

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


class Severity(str, Enum):
    """Severity levels used by remediation requests"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(str, Enum):
    """Common violation categories"""
    DATA_RETENTION = "data_retention"
    DATA_ACCESS = "data_access"
    DATA_BREACH = "data_breach"
    PRIVACY_REQUEST = "privacy_request"
    SECURITY_INCIDENT = "security_incident"


class RemediationRequest(BaseModel):
    """Lightweight model used in integration tests for request payloads."""

    violation_id: str = Field(..., description="Identifier for the violation triggering remediation")
    violation_type: ViolationType = Field(..., description="High level classification for the violation")
    severity: Severity = Field(Severity.MEDIUM, description="Severity level of the violation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual details")

    def is_high_priority(self) -> bool:
        """Return True when severity warrants expedited remediation."""

        return self.severity in {Severity.HIGH, Severity.CRITICAL}


class RemediationDecision(BaseModel):
    """Represents a decision on how to remediate a compliance violation."""

    violation_id: Optional[str] = Field(None, description="ID of the related compliance violation")
    activity_id: Optional[str] = Field(None, description="ID of the related activity")
    remediation_type: RemediationType = Field(
        RemediationType.HUMAN_IN_LOOP, description="Type of remediation approach"
    )
    decision_type: RemediationType = Field(
        RemediationType.HUMAN_IN_LOOP, description="Alias for remediation type used in reporting"
    )
    confidence_score: float = Field(
        0.7, ge=0.0, le=1.0, description="Confidence in the decision"
    )
    reasoning: str = Field("Decision rationale not provided", description="Explanation of the decision logic")
    estimated_effort: int = Field(
        60, ge=0, description="Estimated effort in minutes"
    )
    risk_if_delayed: RiskLevel = Field(
        RiskLevel.MEDIUM, description="Risk level if remediation is delayed"
    )
    prerequisites: List[str] = Field(
        default_factory=list, description="Prerequisites before remediation can start"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Suggested steps that accompany the decision"
    )
    auto_approve: bool = Field(False, description="Whether the decision can be auto-approved")
    requires_human_approval: bool = Field(False, description="Whether human approval is required")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=utc_now, description="Timestamp of decision creation")

    @model_validator(mode="before")
    @classmethod
    def _normalise_inputs(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(values, dict):
            return values

        # Support external aliases
        if "rationale" in values and "reasoning" not in values:
            values["reasoning"] = values.pop("rationale")

        if "risk_level" in values and "risk_if_delayed" not in values:
            values["risk_if_delayed"] = values.pop("risk_level")

        if "estimated_duration" in values and "estimated_effort" not in values:
            values["estimated_effort"] = values.pop("estimated_duration")

        if "decision_type" in values and "remediation_type" not in values:
            values["remediation_type"] = values["decision_type"]

        if "remediation_type" in values and isinstance(values["remediation_type"], str):
            values["remediation_type"] = RemediationType(values["remediation_type"].lower())

        if "decision_type" in values and isinstance(values["decision_type"], str):
            values["decision_type"] = RemediationType(values["decision_type"].lower())

        if "risk_if_delayed" in values and isinstance(values["risk_if_delayed"], str):
            values["risk_if_delayed"] = RiskLevel(values["risk_if_delayed"].lower())

        if "confidence_score" in values:
            try:
                values["confidence_score"] = float(values["confidence_score"])
            except (TypeError, ValueError):
                values["confidence_score"] = 0.7

        return values

    @model_validator(mode="after")
    def _sync_decision_type(self) -> "RemediationDecision":
        if self.decision_type != self.remediation_type:
            self.decision_type = self.remediation_type

        self.auto_approve = self.auto_approve or self.remediation_type == RemediationType.AUTOMATIC

        return self


class WorkflowStep(BaseModel):
    """Model for individual workflow steps"""
    id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="Step description")
    action_type: str = Field(..., description="Type of action (api_call, data_update, notification)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Step status")
    error_message: Optional[str] = Field(None, description="Error message if step failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    estimated_duration_minutes: int = Field(default=5, ge=0, description="Estimated duration in minutes")
    expected_duration: Optional[int] = Field(
        None, ge=0, description="Optional alias for estimated duration"
    )
    step_type: str = Field("automated", description="Categorisation of the workflow step")
    requires_human_approval: bool = Field(False, description="Whether human approval is needed")
    dependencies: List[str] = Field(default_factory=list, description="IDs of prerequisite steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Auxiliary metadata for the step")
    created_at: datetime = Field(default_factory=utc_now, description="Step creation timestamp")
    order: int = Field(default=0, ge=0, description="Step execution order")

    @model_validator(mode="before")
    @classmethod
    def _normalise_inputs(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(values, dict):
            return values

        if "expected_duration" in values and values["expected_duration"] is not None:
            values.setdefault("estimated_duration_minutes", values["expected_duration"])

        if values.get("estimated_duration_minutes") is None:
            values["estimated_duration_minutes"] = 5

        return values

    @model_validator(mode="after")
    def _sync_expected_duration(self) -> "WorkflowStep":
        self.expected_duration = self.estimated_duration_minutes
        return self

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
        default_factory=list, description="Ordered list of workflow steps"
    )
    current_step_index: int = Field(
        default=0, ge=0, description="Index of the currently executing step"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional workflow metadata"
    )
    priority: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Priority level of the workflow"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="When the workflow was created"
    )
    started_at: Optional[datetime] = Field(None, description="When workflow execution began")
    completed_at: Optional[datetime] = Field(None, description="When workflow completed")
    total_estimated_duration: int = Field(
        default=0, ge=0, description="Aggregated estimated duration across steps"
    )
    sqs_queue_url: Optional[str] = Field(None, description="Associated SQS queue URL if created")
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Runtime metadata captured during execution"
    )

    @model_validator(mode="after")
    def _update_duration(self) -> "RemediationWorkflow":
        if not self.total_estimated_duration:
            self.total_estimated_duration = sum(
                step.estimated_duration_minutes for step in self.steps
            )
        return self


class RemediationSignal(BaseModel):
    """Represents a signal indicating need for remediation action."""

    signal_id: str = Field(..., description="Unique identifier for the signal")
    violation_id: Optional[str] = Field(
        None, description="ID of the compliance violation"
    )
    activity_id: Optional[str] = Field(None, description="ID of the related activity")
    signal_type: SignalType = Field(
        SignalType.COMPLIANCE_VIOLATION, description="Type of remediation signal"
    )
    confidence_score: float = Field(
        0.5, ge=0.0, le=1.0, description="Confidence in the signal"
    )
    urgency_level: UrgencyLevel = Field(
        UrgencyLevel.MEDIUM, description="How urgent the remediation is"
    )
    detected_violations: List[str] = Field(
        default_factory=list, description="List of detected violations"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Recommended remediation actions"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the signal"
    )
    framework: Optional[str] = Field(None, description="Regulatory framework context")
    id: Optional[str] = Field(None, description="Unique identifier alias")
    priority: str = Field("medium", description="Priority level derived from risk")
    status: WorkflowStatus = Field(
        WorkflowStatus.PENDING, description="Current processing status"
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="When the signal was created"
    )
    violation: Optional[ComplianceViolation] = Field(
        default=None, description="The related compliance violation object"
    )
    activity: Optional[DataProcessingActivity] = Field(
        default=None, description="The related data processing activity object"
    )
    decision: Optional[RemediationDecision] = Field(
        default=None, description="Decision associated with this signal"
    )
    validation: Optional[Dict[str, Any]] = Field(
        default=None, description="Validation results associated with the signal"
    )
    workflow_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Summary of workflow execution for the signal"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalise_inputs(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(values, dict):
            return values

        if "signal_id" not in values or not values["signal_id"]:
            values["signal_id"] = f"signal_{uuid.uuid4().hex[:8]}"

        if "id" not in values or not values["id"]:
            values["id"] = values["signal_id"]

        violation_obj = values.get("violation")
        if violation_obj and not values.get("violation_id"):
            values["violation_id"] = getattr(violation_obj, "rule_id", None)

        activity_obj = values.get("activity")
        if activity_obj and not values.get("activity_id"):
            values["activity_id"] = getattr(activity_obj, "id", None)

        if "priority" in values:
            priority_value = values["priority"]
            if isinstance(priority_value, RiskLevel):
                values["priority"] = priority_value.value
            else:
                values["priority"] = str(priority_value).lower()
        else:
            values["priority"] = RiskLevel.MEDIUM.value

        return values

    @model_validator(mode="after")
    def _ensure_defaults(self) -> "RemediationSignal":
        self.id = self.id or self.signal_id

        if not self.violation and self.violation_id:
            self.violation = ComplianceViolation(
                rule_id=self.violation_id,
                activity_id=self.activity_id or "unknown",
                description="Auto-generated violation placeholder",
                risk_level=RiskLevel.MEDIUM,
                remediation_actions=[],
            )

        if not self.activity and self.activity_id:
            self.activity = DataProcessingActivity(
                id=self.activity_id,
                name="Auto-generated activity",
                purpose="unspecified",
            )

        return self


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
        default_factory=list, description="List of instructions for completing the task"
    )
    required_approvals: List[str] = Field(
        default_factory=list, description="List of required approvals for this task"
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
