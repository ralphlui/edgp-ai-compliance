"""
Remediation API Router

This router handles remediation requests from the compliance engine
and orchestrates the remediation agent workflow.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from starlette.status import HTTP_200_OK, HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST

from ...models.compliance_models import (
    ComplianceViolation,
    DataProcessingActivity,
    DataType,
    RiskLevel
)
try:
    # Try relative import first
    from ....remediation_agent.main import RemediationAgent
    from ....remediation_agent.state.models import RemediationType
except ImportError:
    # Fallback to absolute import
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.remediation_agent.main import RemediationAgent
    from src.remediation_agent.state.models import RemediationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])

# Initialize remediation agent (singleton pattern)
_remediation_agent: Optional[RemediationAgent] = None


def get_remediation_agent() -> RemediationAgent:
    """Get or create remediation agent instance"""
    global _remediation_agent
    if _remediation_agent is None:
        _remediation_agent = RemediationAgent()
    return _remediation_agent


class RemediationRequest(BaseModel):
    """Request model for remediation trigger"""
    id: str = Field(..., description="Unique identifier for the remediation request")
    action: str = Field(..., description="Action to be performed (e.g., 'delete', 'update', 'anonymize')")
    message: str = Field("", description="Additional message or context")
    field_name: str = Field("", description="Specific field name affected")
    from_value: str = Field("", description="Original value (for updates)")
    to_value: str = Field("", description="Target value (for updates)")
    domain_name: str = Field(..., description="Domain name (e.g., 'customer', 'employee')")

    # Optional override fields
    urgency: Optional[RiskLevel] = Field(None, description="Override urgency level")
    framework: Optional[str] = Field("gdpr_eu", description="Compliance framework")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    data_types: Optional[list[str]] = Field(None, description="Override data types")


class RemediationResponse(BaseModel):
    """Response model for remediation request"""
    success: bool
    request_id: str
    workflow_id: Optional[str] = None
    status: str
    message: str
    decision_type: Optional[str] = None
    estimated_completion: Optional[str] = None
    next_steps: list[str] = Field(default_factory=list)


class SQSMessage(BaseModel):
    """SQS message format for remediation decisions"""
    mode: str  # "auto" or "manual"
    data: Dict[str, Any]


@router.post("/trigger", response_model=RemediationResponse, status_code=HTTP_202_ACCEPTED)
async def trigger_remediation(
    request: RemediationRequest,
    background_tasks: BackgroundTasks,
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """
    Trigger a remediation process based on compliance violation

    This endpoint receives remediation requests from the compliance engine
    and initiates the intelligent remediation workflow.
    """
    logger.info(f"🚀 [REMEDIATION-FLOW-START] Received remediation request: {request.id}")
    logger.info(f"📋 [REQUEST-DETAILS] Action: {request.action}, Domain: {request.domain_name}, Framework: {request.framework}")
    logger.info(f"🔍 [REQUEST-CONTEXT] Field: {request.field_name}, User: {request.user_id}, Urgency: {request.urgency}")
    logger.info(f"💬 [REQUEST-MESSAGE] {request.message}")

    try:
        # Validate request
        logger.info(f"✅ [VALIDATION] Validating request fields for {request.id}")
        if not request.id or not request.action or not request.domain_name:
            logger.error(f"❌ [VALIDATION-FAILED] Missing required fields for request {request.id}")
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Missing required fields: id, action, or domain_name"
            )
        logger.info(f"✅ [VALIDATION-SUCCESS] All required fields present for {request.id}")

        # Convert request to compliance violation and activity
        logger.info(f"🔄 [MODEL-CONVERSION] Converting request {request.id} to compliance models")
        violation, activity = _convert_request_to_models(request)
        logger.info(f"📊 [MODEL-CREATED] Violation ID: {violation.rule_id}, Activity ID: {activity.id}")
        logger.info(f"⚠️ [RISK-LEVEL] {violation.risk_level.value}, Data Types: {[dt.value for dt in activity.data_types]}")

        # Add background task to process remediation
        logger.info(f"🔄 [ASYNC-QUEUE] Queuing background task for remediation processing: {request.id}")
        background_tasks.add_task(
            _process_remediation_async,
            request,
            violation,
            activity,
            agent
        )
        logger.info(f"✅ [ASYNC-QUEUED] Background task successfully queued for {request.id}")

        # Return immediate response
        logger.info(f"📤 [RESPONSE-SENT] Sending acceptance response for {request.id}")
        return RemediationResponse(
            success=True,
            request_id=request.id,
            status="accepted",
            message=f"Remediation request {request.id} accepted and queued for processing",
            next_steps=["Request queued", "Analysis in progress", "Decision will be made shortly"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing remediation request {request.id}: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to process remediation request: {str(e)}"
        )


@router.get("/status/{request_id}", response_model=Dict[str, Any])
async def get_remediation_status(
    request_id: str,
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """Get the status of a remediation request"""

    try:
        # Get workflow status from the agent
        status_result = await agent.get_workflow_status(request_id)

        if not status_result.get("found", False):
            raise HTTPException(
                status_code=404,
                detail=f"Remediation request {request_id} not found"
            )

        workflow_summary = status_result.get("workflow_summary", {})

        return {
            "request_id": request_id,
            "found": True,
            "status": workflow_summary.get("status", "unknown"),
            "workflow_id": workflow_summary.get("id"),
            "created_at": workflow_summary.get("created_at"),
            "completed_at": workflow_summary.get("completed_at"),
            "progress": {
                "total_steps": workflow_summary.get("steps_total", 0),
                "completed_steps": workflow_summary.get("steps_completed", 0),
                "progress_percentage": (
                    (workflow_summary.get("steps_completed", 0) /
                     max(workflow_summary.get("steps_total", 1), 1)) * 100
                )
            },
            "sqs_queue_url": workflow_summary.get("sqs_queue_url"),
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for {request_id}: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to get remediation status: {str(e)}"
        )


@router.post("/resume/{request_id}", response_model=Dict[str, Any])
async def resume_remediation(
    request_id: str,
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """Resume a paused or interrupted remediation workflow"""

    try:
        result = await agent.resume_workflow(request_id)

        return {
            "request_id": request_id,
            "resumed": result.get("success", False),
            "message": "Workflow resumed successfully" if result.get("success") else result.get("error"),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error resuming workflow {request_id}: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to resume remediation: {str(e)}"
        )


@router.delete("/stop/{request_id}")
async def emergency_stop_remediation(
    request_id: str,
    reason: str = "Emergency stop requested",
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """Emergency stop for a remediation workflow"""

    try:
        result = await agent.emergency_stop_workflow(request_id, reason)

        return {
            "request_id": request_id,
            "stopped": result.get("success", False),
            "reason": reason,
            "message": "Workflow stopped successfully" if result.get("success") else result.get("error"),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error stopping workflow {request_id}: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to stop remediation: {str(e)}"
        )


@router.get("/metrics", response_model=Dict[str, Any])
async def get_remediation_metrics(
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """Get current remediation agent metrics"""

    try:
        metrics = await agent.get_agent_metrics()
        active_workflows = await agent.get_active_workflows()

        return {
            "metrics": {
                "total_violations_processed": metrics.total_violations_processed,
                "success_rate": metrics.success_rate,
                "automatic_remediations": metrics.automatic_remediations,
                "human_loop_remediations": metrics.human_loop_remediations,
                "manual_remediations": metrics.manual_remediations,
                "average_resolution_time": metrics.average_resolution_time,
                "by_framework": metrics.by_framework,
                "by_risk_level": metrics.by_risk_level
            },
            "active_workflows": active_workflows,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/graph", response_model=Dict[str, Any])
async def get_graph_visualization(
    agent: RemediationAgent = Depends(get_remediation_agent)
):
    """Get the LangGraph structure visualization"""

    try:
        visualization = agent.graph.get_graph_visualization()

        return {
            "graph_structure": visualization,
            "ascii_representation": agent.get_graph_ascii(),
            "agent_info": agent.get_agent_info(),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting graph visualization: {str(e)}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Failed to get graph visualization: {str(e)}"
        )


def _convert_request_to_models(request: RemediationRequest) -> tuple[ComplianceViolation, DataProcessingActivity]:
    """Convert remediation request to compliance models"""

    # Generate violation ID
    violation_id = f"remediation_{request.action}_{request.id}"

    # Determine risk level based on action
    risk_level = _determine_risk_level(request.action, request.domain_name)

    # Create remediation actions based on request
    remediation_actions = _generate_remediation_actions(request)

    # Create compliance violation
    violation = ComplianceViolation(
        rule_id=violation_id,
        activity_id=f"activity_{request.domain_name}_{request.id}",
        description=_generate_violation_description(request),
        risk_level=request.urgency or risk_level,
        remediation_actions=remediation_actions,
        detected_at=datetime.utcnow()
    )

    # Determine data types
    data_types = _determine_data_types(request)

    # Create data processing activity
    activity = DataProcessingActivity(
        id=f"activity_{request.domain_name}_{request.id}",
        name=f"{request.domain_name.title()} Data Processing",
        purpose=f"Manage {request.domain_name} data for business operations",
        data_types=data_types,
        legal_bases=["legitimate_interest", "contract"],
        retention_period=365,  # Default 1 year
        recipients=["internal_systems"],
        cross_border_transfers=False,  # Default to false
        automated_decision_making=False  # Default to false
    )

    return violation, activity


def _determine_risk_level(action: str, domain_name: str) -> RiskLevel:
    """Determine risk level based on action and domain"""

    high_risk_actions = ["delete", "purge", "anonymize"]
    sensitive_domains = ["customer", "employee", "patient"]

    if action.lower() in high_risk_actions:
        if domain_name.lower() in sensitive_domains:
            return RiskLevel.HIGH
        else:
            return RiskLevel.MEDIUM
    else:
        return RiskLevel.MEDIUM


def _generate_remediation_actions(request: RemediationRequest) -> list[str]:
    """Generate remediation actions based on request"""

    actions = []

    if request.action.lower() == "delete":
        actions.extend([
            f"Delete {request.field_name or 'data'} from {request.domain_name} records",
            "Verify complete data removal",
            "Update audit logs",
            "Confirm deletion completion"
        ])
    elif request.action.lower() == "update":
        actions.extend([
            f"Update {request.field_name or 'field'} from '{request.from_value}' to '{request.to_value}'",
            "Validate data integrity after update",
            "Update audit trail",
            "Notify relevant systems of changes"
        ])
    elif request.action.lower() == "anonymize":
        actions.extend([
            f"Anonymize {request.field_name or 'personal data'} in {request.domain_name} records",
            "Verify anonymization effectiveness",
            "Update data classification",
            "Document anonymization process"
        ])
    else:
        actions.extend([
            f"Execute {request.action} action on {request.domain_name} data",
            "Validate action completion",
            "Update compliance records"
        ])

    if request.message:
        actions.append(f"Additional context: {request.message}")

    return actions


def _generate_violation_description(request: RemediationRequest) -> str:
    """Generate violation description from request"""

    description = f"Remediation required: {request.action} action needed for {request.domain_name}"

    if request.field_name:
        description += f" (field: {request.field_name})"

    if request.message:
        description += f". Context: {request.message}"

    return description


def _determine_data_types(request: RemediationRequest) -> list[DataType]:
    """Determine data types based on request context"""

    if request.data_types:
        # Convert string data types to enum
        return [DataType(dt) for dt in request.data_types if dt in [dt.value for dt in DataType]]

    # Default data types based on domain
    domain_data_types = {
        "customer": [DataType.PERSONAL_DATA, DataType.BEHAVIORAL_DATA],
        "employee": [DataType.PERSONAL_DATA],
        "patient": [DataType.HEALTH_DATA, DataType.PERSONAL_DATA],
        "financial": [DataType.FINANCIAL_DATA, DataType.PERSONAL_DATA],
        "marketing": [DataType.BEHAVIORAL_DATA, DataType.PERSONAL_DATA]
    }

    return domain_data_types.get(request.domain_name.lower(), [DataType.PERSONAL_DATA])


async def _process_remediation_async(
    request: RemediationRequest,
    violation: ComplianceViolation,
    activity: DataProcessingActivity,
    agent: RemediationAgent
):
    """Process remediation in background and send SQS message"""

    try:
        logger.info(f"🎯 [ASYNC-START] Starting async remediation processing for {request.id}")
        logger.info(f"📊 [ASYNC-INPUT] Violation: {violation.rule_id}, Activity: {activity.id}")
        logger.info(f"🔧 [ASYNC-CONFIG] Framework: {request.framework or 'gdpr_eu'}, Urgency: {request.urgency}")

        # Process through remediation agent
        logger.info(f"🤖 [AGENT-INVOKE] Calling RemediationAgent.process_compliance_violation for {request.id}")
        result = await agent.process_compliance_violation(
            violation=violation,
            activity=activity,
            framework=request.framework or "gdpr_eu",
            urgency=request.urgency,
            context={
                "original_request": request.dict(),
                "user_id": request.user_id,
                "field_name": request.field_name,
                "from_value": request.from_value,
                "to_value": request.to_value
            }
        )
        logger.info(f"✅ [AGENT-COMPLETE] RemediationAgent processing completed for {request.id}")
        logger.info(f"📈 [AGENT-RESULT] Keys in result: {list(result.keys())}")

        # Determine mode based on decision
        decision_info = result.get("decision_info", {})
        remediation_type = decision_info.get("remediation_type", "manual_only")
        confidence_score = decision_info.get("confidence_score", 0.0)

        logger.info(f"🎯 [DECISION-INFO] Type: {remediation_type}, Confidence: {confidence_score}")
        logger.info(f"🤔 [DECISION-REASONING] {decision_info.get('reasoning', 'No reasoning provided')}")

        mode = "auto" if remediation_type == "automatic" else "manual"
        logger.info(f"🔀 [MODE-DETERMINED] Remediation mode: {mode} (based on type: {remediation_type})")

        # Create SQS message
        logger.info(f"📝 [SQS-MESSAGE-CREATE] Creating SQS message for {request.id}")
        sqs_message = SQSMessage(
            mode=mode,
            data=request.dict()
        )
        logger.info(f"📋 [SQS-MESSAGE-DETAILS] Mode: {mode}, Data keys: {list(sqs_message.data.keys())}")

        # Send to SQS queue
        workflow_info = result.get("workflow_info", {})
        sqs_queue_url = workflow_info.get("sqs_queue_url")
        workflow_id = workflow_info.get("workflow_id")

        logger.info(f"🔗 [WORKFLOW-INFO] ID: {workflow_id}, Queue URL: {sqs_queue_url}")

        if sqs_queue_url:
            logger.info(f"📡 [SQS-SEND-START] Sending message to SQS queue for {request.id}")
            # Use the SQS tool from the agent
            sqs_tool = agent.graph.workflow_node.sqs_tool

            send_result = await sqs_tool.send_workflow_message(
                queue_url=sqs_queue_url,
                message_body=sqs_message.dict()
            )

            if send_result.get("success"):
                message_id = send_result.get("message_id")
                logger.info(f"✅ [SQS-SEND-SUCCESS] Message sent successfully for {request.id}")
                logger.info(f"🆔 [SQS-MESSAGE-ID] {message_id}")
                logger.info(f"📊 [SQS-QUEUE-INFO] Queue: {sqs_queue_url}")
                logger.info(f"🎯 [SQS-MODE] {mode}")
            else:
                error_msg = send_result.get('error', 'Unknown error')
                logger.error(f"❌ [SQS-SEND-FAILED] Failed to send SQS message for {request.id}: {error_msg}")
        else:
            logger.warning(f"⚠️ [SQS-NO-QUEUE] No SQS queue URL available for {request.id}")

        logger.info(f"🎉 [ASYNC-COMPLETE] Remediation processing completed for {request.id}: {mode} mode")
        logger.info(f"🚀 [REMEDIATION-FLOW-END] Full remediation flow completed for {request.id}")

    except Exception as e:
        logger.error(f"💥 [ASYNC-ERROR] Error in async remediation processing for {request.id}: {str(e)}")
        logger.error(f"📊 [ERROR-CONTEXT] Type: {type(e).__name__}")
        import traceback
        logger.error(f"🔍 [ERROR-TRACEBACK] {traceback.format_exc()}")
        raise