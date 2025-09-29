"""
Analysis Node for LangGraph remediation workflow

This node analyzes incoming compliance violations and determines
the complexity and requirements for remediation.
"""

import logging
from typing import Dict, Any, List

from ...agents.validation_agent import ValidationAgent
from ...state.remediation_state import RemediationState
from ...state.models import RemediationDecision, RemediationType

logger = logging.getLogger(__name__)


class AnalysisNode:
    """
    LangGraph node for analyzing compliance violations and assessing
    remediation complexity and feasibility.
    """

    def __init__(self):
        self.validation_agent = ValidationAgent()

    async def __call__(self, state: RemediationState) -> RemediationState:
        """
        Execute the analysis node

        Args:
            state: Current remediation state

        Returns:
            Updated state with analysis results
        """
        violation_id = state['signal'].violation.rule_id
        logger.info(f"🔍 [ANALYSIS-START] Executing analysis node for violation {violation_id}")
        logger.info(f"📊 [ANALYSIS-INPUT] Signal for violation: {state['signal'].violation.rule_id}, Priority: {state['signal'].urgency.value}")

        try:
            # Add to execution path
            logger.info(f"📝 [EXECUTION-PATH] Adding 'analysis_started' to execution path")
            state["execution_path"].append("analysis_started")

            # Perform complexity assessment
            logger.info(f"🧮 [COMPLEXITY-ASSESS] Starting complexity assessment for {violation_id}")
            complexity_assessment = await self._assess_complexity(state)
            state["complexity_assessment"] = complexity_assessment

            overall_complexity = complexity_assessment.get("overall_complexity", 0.5)
            complexity_factors = complexity_assessment.get("factors", {})
            logger.info(f"📈 [COMPLEXITY-RESULT] Overall complexity: {overall_complexity:.2f}")
            logger.info(f"🔍 [COMPLEXITY-FACTORS] {list(complexity_factors.keys())}")

            # Calculate feasibility score
            logger.info(f"⚖️ [FEASIBILITY-CALC] Calculating feasibility score for {violation_id}")
            feasibility_score = await self._calculate_feasibility(state, complexity_assessment)
            state["feasibility_score"] = feasibility_score
            logger.info(f"🎯 [FEASIBILITY-RESULT] Feasibility score: {feasibility_score:.2f}")

            # Update context with analysis results
            logger.info(f"📝 [CONTEXT-UPDATE] Updating state context with analysis results")
            context_update = {
                "analysis_completed": True,
                "complexity_score": complexity_assessment.get("overall_complexity", 0.5),
                "feasibility_score": feasibility_score,
                "analysis_timestamp": str(state["signal"].received_at)
            }
            state["context"].update(context_update)
            logger.info(f"✅ [CONTEXT-UPDATED] Added keys: {list(context_update.keys())}")

            logger.info(f"📝 [EXECUTION-PATH] Adding 'analysis_completed' to execution path")
            state["execution_path"].append("analysis_completed")
            logger.info(f"Analysis completed: complexity={complexity_assessment.get('overall_complexity'):.2f}, "
                       f"feasibility={feasibility_score:.2f}")

            return state

        except Exception as e:
            logger.error(f"Error in analysis node: {str(e)}")
            state["errors"].append(f"Analysis error: {str(e)}")
            state["execution_path"].append("analysis_failed")
            return state

    async def _assess_complexity(self, state: RemediationState) -> Dict[str, Any]:
        """Assess the complexity of the remediation requirement"""

        signal = state["signal"]
        violation = signal.violation
        activity = signal.activity

        # Data complexity factors
        data_complexity = self._assess_data_complexity(activity.data_types, signal.urgency)

        # Technical complexity factors
        technical_complexity = self._assess_technical_complexity(
            activity, violation.remediation_actions
        )

        # Regulatory complexity factors
        regulatory_complexity = self._assess_regulatory_complexity(
            signal.framework, violation.risk_level
        )

        # Cross-system impact
        system_impact = self._assess_system_impact(activity, violation.remediation_actions)

        # Calculate overall complexity
        complexity_weights = {
            "data": 0.25,
            "technical": 0.30,
            "regulatory": 0.25,
            "system_impact": 0.20
        }

        overall_complexity = (
            data_complexity * complexity_weights["data"] +
            technical_complexity * complexity_weights["technical"] +
            regulatory_complexity * complexity_weights["regulatory"] +
            system_impact * complexity_weights["system_impact"]
        )

        complexity_assessment = {
            "data_complexity": data_complexity,
            "technical_complexity": technical_complexity,
            "regulatory_complexity": regulatory_complexity,
            "system_impact": system_impact,
            "overall_complexity": overall_complexity,
            "complexity_factors": self._identify_complexity_factors(signal),
            "assessment_timestamp": str(signal.received_at)
        }

        return complexity_assessment

    def _assess_data_complexity(self, data_types, urgency) -> float:
        """Assess complexity based on data types involved"""

        # Data type complexity scores
        data_type_scores = {
            "personal_data": 0.3,
            "sensitive_data": 0.6,
            "financial_data": 0.7,
            "health_data": 0.8,
            "biometric_data": 0.9,
            "location_data": 0.4,
            "behavioral_data": 0.5
        }

        if not data_types:
            return 0.2

        # Calculate weighted score based on data types
        max_score = max(data_type_scores.get(dt.value, 0.3) for dt in data_types)
        avg_score = sum(data_type_scores.get(dt.value, 0.3) for dt in data_types) / len(data_types)

        # Weight by number of data types
        variety_factor = min(len(data_types) / 5.0, 1.0)  # Cap at 5 types

        # Urgency factor
        urgency_factors = {"low": 0.8, "medium": 1.0, "high": 1.2, "critical": 1.5}
        urgency_factor = urgency_factors.get(urgency.value, 1.0)

        return min(1.0, (max_score * 0.6 + avg_score * 0.4) * (1 + variety_factor * 0.2) * urgency_factor)

    def _assess_technical_complexity(self, activity, remediation_actions) -> float:
        """Assess technical complexity of remediation"""

        complexity_score = 0.2  # Base complexity

        # Cross-border transfers add complexity
        if activity.cross_border_transfers:
            complexity_score += 0.2

        # Automated decision making adds complexity
        if activity.automated_decision_making:
            complexity_score += 0.2

        # Multiple recipients add complexity
        if len(activity.recipients) > 2:
            complexity_score += 0.1 * min(len(activity.recipients) - 2, 3)

        # Assess remediation action complexity
        action_complexity = self._assess_action_complexity(remediation_actions)
        complexity_score += action_complexity * 0.3

        return min(1.0, complexity_score)

    def _assess_action_complexity(self, remediation_actions) -> float:
        """Assess complexity of remediation actions"""

        if not remediation_actions:
            return 0.0

        # Action complexity mapping
        complex_keywords = {
            "delete": 0.6, "purge": 0.8, "anonymize": 0.9,
            "transfer": 0.5, "migrate": 0.6, "transform": 0.7,
            "encrypt": 0.4, "hash": 0.4, "pseudonymize": 0.6
        }

        moderate_keywords = {
            "update": 0.3, "modify": 0.4, "correct": 0.3,
            "notify": 0.2, "inform": 0.2, "contact": 0.2
        }

        simple_keywords = {
            "review": 0.1, "audit": 0.2, "document": 0.1
        }

        total_complexity = 0.0
        action_count = 0

        for action in remediation_actions:
            action_lower = action.lower()
            action_complexity = 0.2  # Default

            # Check for complex actions
            for keyword, score in complex_keywords.items():
                if keyword in action_lower:
                    action_complexity = max(action_complexity, score)

            # Check for moderate actions
            for keyword, score in moderate_keywords.items():
                if keyword in action_lower:
                    action_complexity = max(action_complexity, score)

            # Check for simple actions
            for keyword, score in simple_keywords.items():
                if keyword in action_lower:
                    action_complexity = max(action_complexity, score)

            total_complexity += action_complexity
            action_count += 1

        return total_complexity / action_count if action_count > 0 else 0.2

    def _assess_regulatory_complexity(self, framework, risk_level) -> float:
        """Assess regulatory complexity"""

        # Framework complexity scores
        framework_scores = {
            "gdpr_eu": 0.8,
            "pdpa_singapore": 0.6,
            "ccpa_california": 0.7,
            "pipeda_canada": 0.5,
            "lgpd_brazil": 0.6
        }

        # Risk level factors
        risk_factors = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.8,
            "critical": 1.0
        }

        framework_score = framework_scores.get(framework, 0.5)
        risk_factor = risk_factors.get(risk_level.value, 0.5)

        return min(1.0, framework_score * risk_factor)

    def _assess_system_impact(self, activity, remediation_actions) -> float:
        """Assess cross-system impact"""

        impact_score = 0.1  # Base impact

        # Number of systems potentially affected
        system_indicators = len(activity.recipients) + len(activity.legal_bases)
        impact_score += min(system_indicators * 0.1, 0.4)

        # Cross-border systems
        if activity.cross_border_transfers:
            impact_score += 0.2

        # Automated systems
        if activity.automated_decision_making:
            impact_score += 0.2

        # Action-based system impact
        high_impact_actions = ["delete", "transfer", "migrate", "anonymize"]
        for action in remediation_actions:
            if any(keyword in action.lower() for keyword in high_impact_actions):
                impact_score += 0.1

        return min(1.0, impact_score)

    def _identify_complexity_factors(self, signal) -> List[str]:
        """Identify specific complexity factors"""

        factors = []

        activity = signal.activity
        violation = signal.violation

        # Data-related factors
        if len(activity.data_types) > 3:
            factors.append("Multiple data types involved")

        sensitive_data_types = {"sensitive_data", "health_data", "biometric_data", "financial_data"}
        if any(dt.value in sensitive_data_types for dt in activity.data_types):
            factors.append("Sensitive data types involved")

        # Technical factors
        if activity.cross_border_transfers:
            factors.append("Cross-border data transfers")

        if activity.automated_decision_making:
            factors.append("Automated decision making systems affected")

        if len(activity.recipients) > 2:
            factors.append(f"Multiple data recipients ({len(activity.recipients)})")

        # Regulatory factors
        if violation.risk_level.value in ["high", "critical"]:
            factors.append(f"High risk level: {violation.risk_level.value}")

        if len(violation.remediation_actions) > 3:
            factors.append("Multiple remediation actions required")

        # Timeline factors
        if signal.urgency.value == "critical":
            factors.append("Critical urgency requirement")

        return factors

    async def _calculate_feasibility(
        self,
        state: RemediationState,
        complexity_assessment: Dict[str, Any]
    ) -> float:
        """Calculate feasibility score for automatic remediation"""

        signal = state["signal"]

        # Use validation agent for detailed feasibility analysis
        dummy_decision = RemediationDecision(
            violation_id=signal.violation.rule_id,
            remediation_type=RemediationType.AUTOMATIC,
            confidence_score=0.5,
            reasoning="Preliminary assessment",
            estimated_effort=60,
            risk_if_delayed=signal.violation.risk_level,
            prerequisites=[]
        )

        feasibility_score, _ = await self.validation_agent.validate_remediation_feasibility(
            signal, dummy_decision
        )

        # Adjust based on complexity
        complexity_penalty = complexity_assessment["overall_complexity"] * 0.3
        adjusted_feasibility = max(0.0, feasibility_score - complexity_penalty)

        return adjusted_feasibility