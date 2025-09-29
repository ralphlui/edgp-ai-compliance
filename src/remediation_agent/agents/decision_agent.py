"""
Decision Agent for determining remediation approach

This agent analyzes compliance violations and decides whether they can be
remediated automatically, require human-in-the-loop, or need manual intervention.
"""

import logging
from typing import Dict, Any, List
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
from compliance_agent.models.compliance_models import (
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

    async def analyze_violation(self, signal: RemediationSignal) -> RemediationDecision:
        """
        Analyze a compliance violation and determine the best remediation approach

        Args:
            signal: The remediation signal containing violation and activity details

        Returns:
            RemediationDecision with the recommended approach
        """
        logger.info(f"Analyzing violation {signal.violation.rule_id} for remediation decision")

        try:
            # Calculate complexity scores
            complexity_analysis = self._analyze_complexity(signal)

            # Prepare prompt variables
            prompt_vars = {
                "rule_id": signal.violation.rule_id,
                "violation_description": signal.violation.description,
                "risk_level": signal.violation.risk_level,
                "remediation_actions": ", ".join(signal.violation.remediation_actions),
                "activity_purpose": signal.activity.purpose,
                "data_types": ", ".join([dt.value for dt in signal.activity.data_types]),
                "legal_bases": ", ".join(signal.activity.legal_bases),
                "cross_border": signal.activity.cross_border_transfers,
                "automated_decisions": signal.activity.automated_decision_making,
                **complexity_analysis
            }

            # Get LLM decision with enhanced error handling
            try:
                messages = self.decision_prompt.format_messages(**prompt_vars)
                response = await self.llm.agenerate([messages])

                if not response or not response.generations or not response.generations[0]:
                    raise ValueError("Empty response from LLM")

                llm_text = response.generations[0][0].text
                logger.info(f"LLM response received: {llm_text[:200]}...")

                # Parse the response
                decision_data = self._parse_llm_response(llm_text)

                # Validate decision data
                if not self._validate_decision_data(decision_data):
                    logger.warning("Invalid decision data from LLM, using rule-based fallback")
                    return self._create_rule_based_decision(signal, complexity_analysis)

            except Exception as llm_error:
                logger.error(f"LLM decision failed: {str(llm_error)}")
                logger.info("Falling back to rule-based decision making")
                return self._create_rule_based_decision(signal, complexity_analysis)

            # Create RemediationDecision object
            decision = RemediationDecision(
                violation_id=signal.violation.rule_id,
                remediation_type=RemediationType(decision_data["remediation_type"].lower()),
                confidence_score=decision_data["confidence_score"],
                reasoning=decision_data["reasoning"],
                estimated_effort=decision_data["estimated_effort"],
                risk_if_delayed=RiskLevel(decision_data["risk_if_delayed"].lower()),
                prerequisites=decision_data.get("prerequisites", [])
            )

            logger.info(f"Decision made for {signal.violation.rule_id}: {decision.remediation_type} "
                       f"(confidence: {decision.confidence_score})")

            return decision

        except Exception as e:
            logger.error(f"Error analyzing violation {signal.violation.rule_id}: {str(e)}")
            # Fallback to conservative decision
            return self._create_fallback_decision(signal)

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
        """Validate LLM decision data"""
        required_fields = ["remediation_type", "confidence_score", "reasoning", "estimated_effort", "risk_if_delayed"]

        if not all(field in decision_data for field in required_fields):
            return False

        # Validate remediation type
        valid_types = ["automatic", "human_in_loop", "manual_only"]
        if decision_data["remediation_type"].lower() not in valid_types:
            return False

        # Validate confidence score
        try:
            confidence = float(decision_data["confidence_score"])
            if not 0.0 <= confidence <= 1.0:
                return False
        except (ValueError, TypeError):
            return False

        # Validate risk level
        valid_risks = ["low", "medium", "high", "critical"]
        if decision_data["risk_if_delayed"].lower() not in valid_risks:
            return False

        return True

    def _create_rule_based_decision(self, signal: RemediationSignal, complexity_analysis: Dict[str, Any]) -> RemediationDecision:
        """Create decision using rule-based logic when LLM fails"""
        logger.info("Creating rule-based decision")

        # Calculate decision factors
        risk_score = self.complexity_weights["risk_levels"][signal.violation.risk_level]
        data_sensitivity = complexity_analysis.get("data_sensitivity_score", 3.0)
        technical_complexity = complexity_analysis.get("technical_complexity", 2.0)
        regulatory_complexity = complexity_analysis.get("regulatory_complexity", 3)

        # Calculate overall complexity score (0-5 scale)
        overall_complexity = (data_sensitivity * 0.3 + technical_complexity * 0.4 + regulatory_complexity * 0.3)

        # Decision logic based on complexity and risk
        if overall_complexity >= 4.0 or risk_score >= 4:
            # High complexity/risk -> Manual only
            remediation_type = RemediationType.MANUAL_ONLY
            confidence = 0.85
            reasoning = f"High complexity ({overall_complexity:.1f}/5) or critical risk requires manual intervention"
            estimated_effort = 180  # 3 hours
            risk_if_delayed = RiskLevel.HIGH

        elif overall_complexity >= 3.0 or risk_score >= 3:
            # Medium complexity/risk -> Human in loop
            remediation_type = RemediationType.HUMAN_IN_LOOP
            confidence = 0.78
            reasoning = f"Medium complexity ({overall_complexity:.1f}/5) requires human oversight"
            estimated_effort = 90  # 1.5 hours
            risk_if_delayed = RiskLevel.MEDIUM

        else:
            # Low complexity/risk -> Automatic
            remediation_type = RemediationType.AUTOMATIC
            confidence = 0.72
            reasoning = f"Low complexity ({overall_complexity:.1f}/5) suitable for automation"
            estimated_effort = 30  # 30 minutes
            risk_if_delayed = RiskLevel.LOW

        # Adjust for specific scenarios
        if "delete" in signal.violation.rule_id.lower() and signal.violation.risk_level == RiskLevel.HIGH:
            remediation_type = RemediationType.HUMAN_IN_LOOP
            reasoning += " - High-risk deletion requires human approval"

        if signal.activity.cross_border_transfers:
            if remediation_type == RemediationType.AUTOMATIC:
                remediation_type = RemediationType.HUMAN_IN_LOOP
                reasoning += " - Cross-border data transfers require oversight"

        logger.info(f"Rule-based decision: {remediation_type.value} (confidence: {confidence:.2f})")

        return RemediationDecision(
            violation_id=signal.violation.rule_id,
            remediation_type=remediation_type,
            confidence_score=confidence,
            reasoning=reasoning,
            estimated_effort=estimated_effort,
            risk_if_delayed=risk_if_delayed,
            prerequisites=self._determine_prerequisites(signal, remediation_type)
        )

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