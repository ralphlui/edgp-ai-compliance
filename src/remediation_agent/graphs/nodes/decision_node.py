"""
Decision Node for LangGraph remediation workflow

This node makes intelligent decisions about remediation approach
based on analysis results and agent recommendations.
"""

import logging
import json
from typing import Dict, Any, List

from ...agents.decision_agent import DecisionAgent
from ...state.remediation_state import RemediationState
from ...state.models import RemediationType, RiskLevel

logger = logging.getLogger(__name__)


class DecisionNode:
    """
    LangGraph node for making remediation decisions based on
    violation analysis and complexity assessment.
    """

    def __init__(self):
        self.decision_agent = DecisionAgent()

        # Decision thresholds
        self.thresholds = {
            "automatic": {
                "min_feasibility": 0.7,
                "max_complexity": 0.6,
                "min_confidence": 0.8,
                "max_risk_level": RiskLevel.MEDIUM
            },
            "human_loop": {
                "min_feasibility": 0.4,
                "max_complexity": 0.8,
                "min_confidence": 0.6,
                "max_risk_level": RiskLevel.HIGH
            }
        }

    async def __call__(self, state: RemediationState) -> RemediationState:
        """
        Execute the decision node

        Args:
            state: Current remediation state

        Returns:
            Updated state with remediation decision
        """
        violation_id = state['signal'].violation.rule_id
        logger.info(f"🤔 [DECISION-START] Executing decision node for violation {violation_id}")
        logger.info(f"🎯 [DECISION-INPUT] Signal for violation: {state['signal'].violation.rule_id}, Risk: {state['signal'].violation.risk_level.value}")

        try:
            # Helper to safely cast floats for logging/comparisons
            def _safe_float(value: Any, default: float) -> float:
                try:
                    if value is None:
                        return default
                    return float(value)
                except (TypeError, ValueError):
                    return default

            # Add to execution path
            logger.info(f"📝 [EXECUTION-PATH] Adding 'decision_started' to execution path")
            state["execution_path"].append("decision_started")

            # Get analysis results
            logger.info(f"📊 [ANALYSIS-DATA] Retrieving analysis results for decision making")
            complexity_assessment = state.get("complexity_assessment") or {}
            feasibility_score = _safe_float(state.get("feasibility_score"), 0.0)

            overall_complexity = _safe_float(
                complexity_assessment.get("overall_complexity"),
                0.5
            )
            logger.info(
                "📈 [ANALYSIS-SCORES] Complexity: %.2f, Feasibility: %.2f",
                overall_complexity,
                feasibility_score,
            )

            signal = state["signal"]
            prompts = state.setdefault("context", {}).setdefault("node_prompts", {})
            decision_prompt = {
                "violation_id": signal.violation.rule_id,
                "risk_level": signal.violation.risk_level.value,
                "framework": signal.framework,
                "urgency": signal.urgency.value,
                "remediation_actions": signal.violation.remediation_actions,
                "analysis": {
                    "overall_complexity": overall_complexity,
                    "feasibility_score": feasibility_score,
                    "complexity_factors": complexity_assessment.get("complexity_factors", [])
                }
            }
            logger.info(
                "🧾 [NODE-PROMPT][decision] %s",
                json.dumps(decision_prompt, default=str)
            )
            prompts["decision"] = decision_prompt

            # Make primary decision using AI agent
            logger.info(f"🤖 [AI-DECISION-START] Calling DecisionAgent.analyze_violation for {violation_id}")
            decision = await self.decision_agent.analyze_violation(state["signal"])
            raw_confidence = _safe_float(decision.confidence_score, 0.0)
            logger.info(
                "🎯 [AI-DECISION-RAW] Type: %s, Confidence: %.2f",
                decision.remediation_type.value,
                raw_confidence,
            )
            logger.info(f"💭 [AI-REASONING] {decision.reasoning}")

            # Validate and potentially override decision based on analysis
            logger.info(f"✅ [DECISION-VALIDATE] Validating and adjusting AI decision based on analysis")
            validated_decision = await self._validate_and_adjust_decision(
                decision, complexity_assessment, feasibility_score, state
            )
            logger.info(f"🔍 [DECISION-VALIDATED] Final type: {validated_decision.remediation_type.value}")
            final_confidence = _safe_float(validated_decision.confidence_score, 0.0)
            logger.info(
                "📊 [DECISION-CONFIDENCE] Final confidence: %.2f",
                final_confidence,
            )

            # Update state with decision
            logger.info(f"📝 [STATE-UPDATE] Storing validated decision in state")
            state["decision"] = validated_decision

            # Update context
            logger.info(f"🔄 [CONTEXT-UPDATE] Updating context with decision information")
            context_update = {
                "decision_made": True,
                "decision_confidence": validated_decision.confidence_score,
                "decision_reasoning": validated_decision.reasoning,
                "decision_type": validated_decision.remediation_type.value
            }
            state["context"].update(context_update)
            logger.info(f"✅ [CONTEXT-UPDATED] Added decision keys: {list(context_update.keys())}")

            # Determine next steps based on decision
            logger.info(f"🗺️ [NEXT-STEPS] Determining next steps for {validated_decision.remediation_type.value}")
            next_steps = self._determine_next_steps(validated_decision)
            state["context"]["next_steps"] = next_steps
            logger.info(f"📋 [NEXT-STEPS-SET] Steps: {next_steps}")

            logger.info(f"📝 [EXECUTION-PATH] Adding 'decision_completed' to execution path")
            state["execution_path"].append("decision_completed")

            logger.info(
                "🎉 [DECISION-COMPLETE] Decision made: %s (confidence: %.2f)",
                validated_decision.remediation_type.value,
                final_confidence,
            )
            logger.info(
                "🧾 [REMEDIATION-DECISION] %s",
                json.dumps(
                    {
                        "violation_id": violation_id,
                        "remediation_type": validated_decision.remediation_type.value,
                        "confidence_score": final_confidence,
                        "estimated_effort": validated_decision.estimated_effort,
                        "risk_if_delayed": validated_decision.risk_if_delayed.value if hasattr(validated_decision.risk_if_delayed, "value") else validated_decision.risk_if_delayed,
                        "reasoning": validated_decision.reasoning,
                        "prerequisites": validated_decision.prerequisites,
                        "recommended_actions": validated_decision.recommended_actions,
                    },
                    default=str
                )
            )
            state["context"]["node_prompts"]["decision_result"] = {
                "remediation_type": validated_decision.remediation_type.value,
                "confidence_score": final_confidence,
                "estimated_effort": validated_decision.estimated_effort,
                "risk_if_delayed": validated_decision.risk_if_delayed.value
                if hasattr(validated_decision.risk_if_delayed, "value")
                else validated_decision.risk_if_delayed,
                "reasoning": validated_decision.reasoning,
            }

            return state

        except Exception as e:
            logger.error(f"Error in decision node: {str(e)}")
            state["errors"].append(f"Decision error: {str(e)}")
            state["execution_path"].append("decision_failed")

            # Create fallback decision
            fallback_decision = self._create_fallback_decision(state)
            state["decision"] = fallback_decision

            return state

    async def _validate_and_adjust_decision(
        self,
        decision,
        complexity_assessment: Dict[str, Any],
        feasibility_score: float,
        state: RemediationState
    ):
        """Validate and potentially adjust the AI agent's decision"""

        original_type = decision.remediation_type
        adjusted_decision = decision

        # Get analysis metrics
        overall_complexity = complexity_assessment.get("overall_complexity", 0.5)
        risk_level = state["signal"].violation.risk_level

        # Apply rule-based validation and adjustment
        adjustment_reason = []

        # Check automatic remediation criteria
        if decision.remediation_type == RemediationType.AUTOMATIC:
            if not self._meets_automatic_criteria(
                feasibility_score, overall_complexity, decision.confidence_score, risk_level
            ):
                adjusted_decision.remediation_type = RemediationType.HUMAN_IN_LOOP
                adjustment_reason.append("Automatic criteria not met - downgraded to human-in-loop")

        # Check human-in-loop criteria
        elif decision.remediation_type == RemediationType.HUMAN_IN_LOOP:
            if not self._meets_human_loop_criteria(
                feasibility_score, overall_complexity, decision.confidence_score, risk_level
            ):
                adjusted_decision.remediation_type = RemediationType.MANUAL_ONLY
                adjustment_reason.append("Human-in-loop criteria not met - downgraded to manual only")

        # Critical risk level override
        if risk_level == RiskLevel.CRITICAL:
            if decision.remediation_type == RemediationType.AUTOMATIC:
                adjusted_decision.remediation_type = RemediationType.HUMAN_IN_LOOP
                adjustment_reason.append("Critical risk level requires human oversight")

        # Very low feasibility override
        if feasibility_score < 0.3:
            if decision.remediation_type in [RemediationType.AUTOMATIC, RemediationType.HUMAN_IN_LOOP]:
                adjusted_decision.remediation_type = RemediationType.MANUAL_ONLY
                adjustment_reason.append("Very low feasibility requires manual approach")

        # Very high complexity override
        if overall_complexity > 0.8:
            if decision.remediation_type == RemediationType.AUTOMATIC:
                adjusted_decision.remediation_type = RemediationType.HUMAN_IN_LOOP
                adjustment_reason.append("High complexity requires human oversight")

        # Update decision confidence based on adjustments
        if adjustment_reason:
            confidence_penalty = len(adjustment_reason) * 0.1
            adjusted_decision.confidence_score = max(0.1, decision.confidence_score - confidence_penalty)

            # Update reasoning
            original_reasoning = adjusted_decision.reasoning
            adjustment_text = "; ".join(adjustment_reason)
            adjusted_decision.reasoning = f"{original_reasoning}\n\nAdjustments: {adjustment_text}"

        # Log adjustments
        if original_type != adjusted_decision.remediation_type:
            logger.info(f"Decision adjusted from {original_type} to {adjusted_decision.remediation_type}: "
                       f"{'; '.join(adjustment_reason)}")

        return adjusted_decision

    def _meets_automatic_criteria(
        self,
        feasibility_score: float,
        complexity: float,
        confidence: float,
        risk_level: RiskLevel
    ) -> bool:
        """Check if criteria for automatic remediation are met"""

        criteria = self.thresholds["automatic"]

        return (
            feasibility_score >= criteria["min_feasibility"] and
            complexity <= criteria["max_complexity"] and
            confidence >= criteria["min_confidence"] and
            self._risk_level_value(risk_level) <= self._risk_level_value(criteria["max_risk_level"])
        )

    def _meets_human_loop_criteria(
        self,
        feasibility_score: float,
        complexity: float,
        confidence: float,
        risk_level: RiskLevel
    ) -> bool:
        """Check if criteria for human-in-loop remediation are met"""

        criteria = self.thresholds["human_loop"]

        return (
            feasibility_score >= criteria["min_feasibility"] and
            complexity <= criteria["max_complexity"] and
            confidence >= criteria["min_confidence"] and
            self._risk_level_value(risk_level) <= self._risk_level_value(criteria["max_risk_level"])
        )

    def _risk_level_value(self, risk_level: RiskLevel) -> int:
        """Convert risk level to numeric value for comparison"""
        risk_values = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        return risk_values.get(risk_level, 2)

    def _determine_next_steps(self, decision) -> List[str]:
        """Determine next steps based on the decision"""

        next_steps = []

        if decision.remediation_type == RemediationType.AUTOMATIC:
            next_steps = [
                "create_workflow",
                "setup_sqs_queue",
                "execute_automated_steps",
                "verify_completion",
                "update_compliance_status"
            ]

        elif decision.remediation_type == RemediationType.HUMAN_IN_LOOP:
            next_steps = [
                "create_workflow",
                "setup_sqs_queue",
                "create_human_tasks",
                "send_notifications",
                "wait_for_human_input",
                "execute_approved_steps",
                "verify_completion"
            ]

        else:  # MANUAL_ONLY
            next_steps = [
                "create_workflow",
                "setup_sqs_queue",
                "create_human_tasks",
                "send_urgent_notifications",
                "assign_to_specialist",
                "track_manual_progress"
            ]

        return next_steps

    def _create_fallback_decision(self, state: RemediationState):
        """Create a safe fallback decision when the main decision process fails"""

        from ...state.models import RemediationDecision

        return RemediationDecision(
            violation_id=state["signal"].violation.rule_id,
            remediation_type=RemediationType.HUMAN_IN_LOOP,  # Conservative default
            confidence_score=0.3,
            reasoning="Fallback decision due to decision process failure - requires human oversight",
            estimated_effort=180,  # Conservative estimate
            risk_if_delayed=state["signal"].violation.risk_level,
            prerequisites=["Manual assessment required", "System verification needed"]
        )

    def should_proceed_to_workflow(self, state: RemediationState) -> bool:
        """Determine if the process should proceed to workflow creation"""

        decision = state.get("decision")
        if not decision:
            return False

        # Always proceed unless there are blocking errors
        blocking_errors = [
            error for error in state.get("errors", [])
            if "critical" in error.lower() or "blocking" in error.lower()
        ]

        return len(blocking_errors) == 0

    def should_require_human_intervention(self, state: RemediationState) -> bool:
        """Determine if human intervention is required at this stage"""

        decision = state.get("decision")
        if not decision:
            return True

        return decision.remediation_type in [
            RemediationType.HUMAN_IN_LOOP,
            RemediationType.MANUAL_ONLY
        ]

    def get_decision_summary(self, state: RemediationState) -> Dict[str, Any]:
        """Get a summary of the decision for logging/reporting"""

        decision = state.get("decision")
        if not decision:
            return {"error": "No decision available"}

        complexity_assessment = state.get("complexity_assessment", {})
        feasibility_score = state.get("feasibility_score", 0.0)

        return {
            "violation_id": decision.violation_id,
            "decision_type": decision.remediation_type.value,
            "confidence_score": decision.confidence_score,
            "estimated_effort": decision.estimated_effort,
            "risk_if_delayed": decision.risk_if_delayed.value,
            "feasibility_score": feasibility_score,
            "overall_complexity": complexity_assessment.get("overall_complexity", 0.0),
            "prerequisites_count": len(decision.prerequisites),
            "reasoning_summary": decision.reasoning[:200] + "..." if len(decision.reasoning) > 200 else decision.reasoning
        }
