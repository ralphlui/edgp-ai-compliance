"""
Decision Agent for determining remediation approach

This agent analyzes compliance violations and decides whether they can be
remediated automatically, require human-in-the-loop, or need manual intervention.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage
import os

# Import settings - handle import gracefully
try:
    from config.settings import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    settings = None

from ..state.models import (
    RemediationSignal,
    RemediationDecision,
    RemediationType,
    RiskLevel
)
from src.compliance_agent.models.compliance_models import (
    ComplianceViolation,
    DataProcessingActivity,
    DataType
)

logger = logging.getLogger(__name__)


class DecisionAgent:
    """
    Agent responsible for analyzing compliance violations and making
    intelligent decisions about remediation approaches.
    """

    def __init__(self, model_name: str = None, temperature: float = None):
        # Get configuration from settings or fallback to parameters/environment
        if SETTINGS_AVAILABLE and settings:
            model_name = model_name or settings.ai_model_name
            temperature = temperature if temperature is not None else settings.ai_temperature
            api_key = settings.openai_api_key
        else:
            model_name = model_name or "gpt-3.5-turbo"
            temperature = temperature if temperature is not None else 0.1
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OpenAI API key not found in settings or environment (OPENAI_API_KEY)")

        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key
        )
        self.decision_prompt = self._create_decision_prompt()

        # Complexity scoring weights
        self.complexity_weights = {
            "data_types": {
                DataType.PERSONAL_DATA: 1,
                DataType.SENSITIVE_DATA: 3,
                DataType.FINANCIAL_DATA: 3,
                DataType.HEALTH_DATA: 4,
                DataType.BIOMETRIC_DATA: 5,
                DataType.LOCATION_DATA: 2,
                DataType.BEHAVIORAL_DATA: 2
            },
            "risk_levels": {
                RiskLevel.LOW: 1,
                RiskLevel.MEDIUM: 2,
                RiskLevel.HIGH: 4,
                RiskLevel.CRITICAL: 5
            }
        }

    async def make_decision(self, signal: RemediationSignal) -> RemediationDecision:
        """Convenience wrapper expected by the enhanced test-suite."""

        return await self.analyze_violation(signal)

    def _create_decision_prompt(self) -> ChatPromptTemplate:
        """Create the prompt template for remediation decisions"""
        template = """
You are an expert AI compliance remediation specialist. Your task is to analyze a compliance violation and determine the best remediation approach.

VIOLATION DETAILS:
Rule ID: {rule_id}
Description: {violation_description}
Risk Level: {risk_level}
Suggested Actions: {remediation_actions}

DATA PROCESSING ACTIVITY:
Purpose: {activity_purpose}
Data Types: {data_types}
Legal Bases: {legal_bases}
Cross-border Transfers: {cross_border}
Automated Decision Making: {automated_decisions}

COMPLEXITY ANALYSIS:
- Data Sensitivity Score: {data_sensitivity_score}
- Technical Complexity: {technical_complexity}
- Regulatory Complexity: {regulatory_complexity}
- Cross-system Impact: {cross_system_impact}

DECISION CRITERIA:
1. AUTOMATIC: Simple violations with clear, standardized fixes that don't require judgment calls
   - Low/medium risk
   - Single system impact
   - Standard remediation actions
   - No regulatory ambiguity

2. HUMAN_IN_LOOP: Complex violations requiring oversight but with some automation potential
   - Medium/high risk
   - Multiple system impact
   - Requires validation or approval
   - Some regulatory interpretation needed

3. MANUAL_ONLY: Critical violations requiring full human expertise
   - High/critical risk
   - Significant business impact
   - Complex regulatory interpretation
   - Legal review required

Please analyze this violation and provide:
1. Recommended remediation type (AUTOMATIC, HUMAN_IN_LOOP, or MANUAL_ONLY)
2. Confidence score (0.0 to 1.0)
3. Detailed reasoning for your decision
4. Estimated effort in minutes
5. Risk if remediation is delayed
6. Any prerequisites needed

Respond in the following JSON format:
{{
    "remediation_type": "<type>",
    "confidence_score": <score>,
    "reasoning": "<detailed explanation>",
    "estimated_effort": <minutes>,
    "risk_if_delayed": "<risk_level>",
    "prerequisites": ["<prerequisite1>", "<prerequisite2>"]
}}
"""
        return ChatPromptTemplate.from_template(template)

    async def _analyze_with_llm(
        self,
        signal: RemediationSignal,
        complexity_details: Dict[str, Any],
        cross_system_impact: str,
    ) -> Dict[str, Any]:
        """Run the LLM-based analysis and return a structured payload."""

        prompt_vars = self._build_prompt_variables(signal, complexity_details, cross_system_impact)
        messages = self.decision_prompt.format_messages(**prompt_vars)

        llm_text: Optional[str] = None
        # Prefer ainvoke when available (matches enhanced tests)
        if hasattr(self.llm, "ainvoke"):
            response = await self.llm.ainvoke(messages)
            llm_text = getattr(response, "content", None)
        else:
            response = await self.llm.agenerate([messages])
            if response and response.generations and response.generations[0]:
                llm_text = response.generations[0][0].text

        if not llm_text:
            raise ValueError("Empty response from LLM")

        logger.info("LLM response received: %s", llm_text[:200])
        return self._parse_llm_response(llm_text)

    def _validate_llm_response(self, payload: Dict[str, Any]) -> bool:
        """Ensure the LLM payload contains all fields with acceptable values."""

        if not isinstance(payload, dict):
            return False

        required_fields = {
            "remediation_type",
            "confidence_score",
            "reasoning",
            "estimated_effort",
            "risk_if_delayed",
        }
        if not required_fields.issubset(payload.keys()):
            return False

        try:
            confidence = float(payload["confidence_score"])
            if not 0.0 <= confidence <= 1.0:
                return False
        except (TypeError, ValueError):
            return False

        try:
            int(payload["estimated_effort"])
        except (TypeError, ValueError):
            return False

        try:
            self._map_string_to_risk_level(str(payload["risk_if_delayed"]))
        except ValueError:
            return False

        return str(payload["remediation_type"]).lower() in {
            r.value for r in RemediationType
        }

    def _assess_complexity(self, actions: Optional[List[str]]) -> Dict[str, Any]:
        """Calculate lightweight complexity metrics for remediation actions."""

        if not actions:
            return {
                "complexity_score": 1.0,
                "automation_patterns": 0,
                "average_length": 0.0,
            }

        action_count = len(actions)
        average_length = sum(len(action) for action in actions) / action_count

        automation_keywords = ("update", "notify", "email", "log", "flag")
        high_risk_keywords = ("delete", "purge", "legal", "regulator", "contract")

        automation_hits = sum(
            1 for action in actions if any(keyword in action.lower() for keyword in automation_keywords)
        )
        high_risk_hits = sum(
            1 for action in actions if any(keyword in action.lower() for keyword in high_risk_keywords)
        )

        complexity_score = min(5.0, 1.0 + (action_count * 0.4) + (high_risk_hits * 0.6))

        return {
            "complexity_score": round(complexity_score, 2),
            "automation_patterns": automation_hits,
            "high_risk_actions": high_risk_hits,
            "average_length": round(average_length, 2),
        }

    def _assess_cross_system_impact(self, signal: RemediationSignal) -> str:
        """Estimate cross-system impact using existing heuristics."""

        return self._estimate_cross_system_impact(signal)

    def _determine_rule_based_decision(
        self,
        signal: RemediationSignal,
        factors: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback rule-based decision used when LLM is unavailable."""

        risk_level = signal.violation.risk_level
        actions = signal.violation.remediation_actions or []

        if risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}:
            decision_type = RemediationType.MANUAL_ONLY if risk_level == RiskLevel.CRITICAL else RemediationType.HUMAN_IN_LOOP
        elif len(actions) >= 3:
            decision_type = RemediationType.HUMAN_IN_LOOP
        else:
            decision_type = RemediationType.AUTOMATIC

        complexity = factors.get("complexity_score", 1.0)

        confidence = self._calculate_confidence_score(
            {
                "risk_level": risk_level,
                "complexity_score": complexity,
                "automation_patterns": factors.get("automation_patterns", 0),
            }
        )

        estimated_effort = self._estimate_effort(actions, complexity)
        risk_if_delayed = self._map_risk_level_to_string(risk_level)
        reasoning = self._get_decision_rationale(decision_type.value, factors)
        prerequisites = self._determine_prerequisites(signal, decision_type)

        return {
            "decision_type": decision_type.value,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "estimated_effort": estimated_effort,
            "risk_if_delayed": risk_if_delayed,
            "prerequisites": prerequisites,
        }

    def _decision_from_payload(
        self,
        signal: RemediationSignal,
        payload: Dict[str, Any],
    ) -> RemediationDecision:
        """Convert decision payload into a RemediationDecision instance."""

        remediation_type = RemediationType(payload["decision_type"].lower())
        risk_level = self._map_string_to_risk_level(payload["risk_if_delayed"])

        return RemediationDecision(
            violation_id=signal.violation.rule_id,
            activity_id=signal.activity.id if signal.activity else None,
            remediation_type=remediation_type,
            decision_type=remediation_type,
            confidence_score=float(payload["confidence_score"]),
            reasoning=str(payload["reasoning"]),
            estimated_effort=int(payload["estimated_effort"]),
            risk_if_delayed=risk_level,
            prerequisites=payload.get("prerequisites", []),
            recommended_actions=payload.get("recommended_actions", []),
        )

    @staticmethod
    def _map_risk_level_to_string(risk: RiskLevel) -> str:
        return risk.value

    @staticmethod
    def _map_string_to_risk_level(value: str) -> RiskLevel:
        try:
            return RiskLevel(value.lower())
        except ValueError as exc:
            raise ValueError("Invalid risk level") from exc

    def _calculate_confidence_score(self, factors: Dict[str, Any]) -> float:
        risk = factors.get("risk_level", RiskLevel.MEDIUM)
        complexity = float(factors.get("complexity_score", 1.0))
        automation_hits = factors.get("automation_patterns", 0)

        base = 0.75 if risk in {RiskLevel.LOW, RiskLevel.MEDIUM} else 0.6
        adjustment = 0.05 * automation_hits
        penalty = 0.06 * max(0, complexity - 2.0)

        score = max(0.2, min(0.95, base + adjustment - penalty))
        return round(score, 2)

    def _estimate_effort(self, actions: List[str], complexity_score: float) -> int:
        action_count = max(1, len(actions))
        base_effort = 20 * action_count
        complexity_multiplier = 1 + (complexity_score / 4)
        return int(base_effort * complexity_multiplier)

    def _get_decision_rationale(self, decision_type: str, factors: Dict[str, Any]) -> str:
        risk = factors.get("risk_level", RiskLevel.MEDIUM)
        complexity = factors.get("complexity_score", 1.0)
        impact = factors.get("cross_system_impact", "low")

        rationale_parts = [
            f"Risk level {risk.value}",
            f"complexity score {complexity}",
            f"cross-system impact {impact}",
        ]

        if decision_type == RemediationType.AUTOMATIC.value:
            rationale_parts.append("suitable for automated execution")
        elif decision_type == RemediationType.HUMAN_IN_LOOP.value:
            rationale_parts.append("requires human verification before completion")
        else:
            rationale_parts.append("requires dedicated manual handling")

        return "; ".join(rationale_parts)

    def _build_prompt_variables(
        self,
        signal: RemediationSignal,
        complexity_details: Dict[str, Any],
        cross_system_impact: str,
    ) -> Dict[str, Any]:
        return {
            "rule_id": signal.violation.rule_id,
            "violation_description": signal.violation.description,
            "risk_level": signal.violation.risk_level.value,
            "remediation_actions": ", ".join(signal.violation.remediation_actions),
            "activity_purpose": signal.activity.purpose if signal.activity else "unspecified",
            "data_types": ", ".join(dt.value for dt in (signal.activity.data_types if signal.activity else [])),
            "legal_bases": ", ".join(signal.activity.legal_bases if signal.activity else []),
            "cross_border": bool(signal.activity.cross_border_transfers) if signal.activity else False,
            "automated_decisions": bool(signal.activity.automated_decision_making) if signal.activity else False,
            "data_sensitivity_score": complexity_details.get("complexity_score", 1.0),
            "technical_complexity": complexity_details.get("average_length", 0) / 10,
            "regulatory_complexity": self.complexity_weights["risk_levels"][signal.violation.risk_level],
            "cross_system_impact": cross_system_impact,
        }

    async def analyze_violation(self, signal: RemediationSignal) -> RemediationDecision:
        """Analyze a compliance violation and determine the best remediation approach."""

        logger.info("Analyzing violation %s for remediation decision", signal.violation.rule_id)

        # Derive contextual factors used across helpers
        complexity_details = self._assess_complexity(signal.violation.remediation_actions)
        cross_system_impact = self._assess_cross_system_impact(signal)
        analysis_factors = {
            "risk_level": signal.violation.risk_level,
            "complexity_score": complexity_details.get("complexity_score", 1.0),
            "automation_patterns": complexity_details.get("automation_patterns", 0),
            "cross_system_impact": cross_system_impact,
        }

        try:
            decision_payload = await self._analyze_with_llm(signal, complexity_details, cross_system_impact)
            if not self._validate_llm_response(decision_payload):
                logger.warning("LLM response failed validation, using rule-based decision")
                decision_payload = self._determine_rule_based_decision(signal, analysis_factors)
        except Exception as exc:
            logger.error("LLM decision failed: %s", exc)
            decision_payload = self._determine_rule_based_decision(signal, analysis_factors)

        return self._decision_from_payload(signal, decision_payload)

    def _analyze_complexity(self, signal: RemediationSignal) -> Dict[str, Any]:
        """Analyze the complexity of the violation and activity"""

        # Data sensitivity score
        data_sensitivity = sum(
            self.complexity_weights["data_types"].get(dt, 1)
            for dt in signal.activity.data_types
        ) / len(signal.activity.data_types) if signal.activity.data_types else 1

        # Technical complexity based on various factors
        technical_factors = [
            2 if signal.activity.cross_border_transfers else 1,
            3 if signal.activity.automated_decision_making else 1,
            len(signal.activity.recipients) if signal.activity.recipients else 1,
            2 if len(signal.activity.data_types) > 3 else 1
        ]
        technical_complexity = sum(technical_factors) / len(technical_factors)

        # Regulatory complexity
        regulatory_complexity = self.complexity_weights["risk_levels"][signal.violation.risk_level]

        # Cross-system impact estimation
        cross_system_impact = self._estimate_cross_system_impact(signal)

        return {
            "data_sensitivity_score": round(data_sensitivity, 2),
            "technical_complexity": round(technical_complexity, 2),
            "regulatory_complexity": regulatory_complexity,
            "cross_system_impact": cross_system_impact
        }

    def _estimate_cross_system_impact(self, signal: RemediationSignal) -> str:
        """Estimate the cross-system impact of remediation"""
        factors = []

        if signal.activity.cross_border_transfers:
            factors.append("cross-border data flows")

        if signal.activity.automated_decision_making:
            factors.append("automated decision systems")

        if len(signal.activity.recipients) > 2:
            factors.append("multiple data recipients")

        if len(signal.violation.remediation_actions) > 3:
            factors.append("multiple remediation steps")

        if len(factors) >= 3:
            return "high"
        elif len(factors) >= 1:
            return "medium"
        else:
            return "low"

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into structured data"""
        import json
        import re

        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback parsing if JSON extraction fails
        logger.warning("Failed to parse LLM response as JSON, using fallback parsing")
        return self._fallback_parse(response)

    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """Fallback parsing for non-JSON responses"""
        # Default to human-in-loop for safety
        return {
            "remediation_type": "HUMAN_IN_LOOP",
            "confidence_score": 0.5,
            "reasoning": "Could not parse LLM response, defaulting to human oversight",
            "estimated_effort": 60,
            "risk_if_delayed": "MEDIUM",
            "prerequisites": ["Manual review required"]
        }

    def _create_fallback_decision(self, signal: RemediationSignal) -> RemediationDecision:
        """Create a conservative fallback decision when analysis fails"""
        return RemediationDecision(
            violation_id=signal.violation.rule_id,
            remediation_type=RemediationType.HUMAN_IN_LOOP,
            confidence_score=0.3,
            reasoning="Analysis failed, defaulting to human oversight for safety",
            estimated_effort=120,
            risk_if_delayed=signal.violation.risk_level,
            prerequisites=["Manual analysis required", "System check needed"]
        )

    def _validate_decision_data(self, decision_data: Dict[str, Any]) -> bool:
        """Backward compatible wrapper for legacy tests."""

        return self._validate_llm_response(decision_data)

    def _create_rule_based_decision(self, signal: RemediationSignal, complexity_analysis: Dict[str, Any]) -> RemediationDecision:
        """Create decision using rule-based logic when LLM fails"""
        logger.info("Creating rule-based decision")

        factors = {
            "risk_level": signal.violation.risk_level,
            "complexity_score": complexity_analysis.get("data_sensitivity_score", 1.0),
            "automation_patterns": len(signal.violation.remediation_actions or []),
            "cross_system_impact": self._estimate_cross_system_impact(signal),
        }

        payload = self._determine_rule_based_decision(signal, factors)
        return self._decision_from_payload(signal, payload)

    def _determine_prerequisites(self, signal: RemediationSignal, remediation_type: RemediationType) -> List[str]:
        """Determine prerequisites based on remediation type and signal characteristics"""
        prerequisites = []

        if remediation_type == RemediationType.MANUAL_ONLY:
            prerequisites.extend([
                "Legal review required",
                "Compliance officer approval",
                "Impact assessment"
            ])

        elif remediation_type == RemediationType.HUMAN_IN_LOOP:
            prerequisites.extend([
                "Human review and approval",
                "Backup and recovery plan"
            ])

        if signal.activity.cross_border_transfers:
            prerequisites.append("Cross-border transfer compliance check")

        if signal.violation.risk_level == RiskLevel.HIGH:
            prerequisites.append("Risk assessment documentation")

        if "delete" in signal.violation.rule_id.lower():
            prerequisites.append("Data retention policy compliance")

        return prerequisites

    def get_decision_criteria(self) -> Dict[str, Any]:
        """Get the decision criteria used by this agent"""
        return {
            "automatic_thresholds": {
                "max_risk_level": "MEDIUM",
                "max_data_sensitivity": 3.0,
                "max_technical_complexity": 2.5,
                "required_confidence": 0.8
            },
            "human_loop_thresholds": {
                "max_risk_level": "HIGH",
                "max_data_sensitivity": 4.0,
                "required_confidence": 0.6
            },
            "complexity_weights": self.complexity_weights
        }
