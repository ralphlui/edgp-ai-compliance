"""Decision agent responsible for choosing remediation strategies."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import openai

from ..state.models import RemediationDecision, RemediationSignal, RemediationType, RiskLevel
from src.compliance_agent.models.compliance_models import DataType

try:  # Optional dependency; safe to ignore during unit tests without settings module
    from config.settings import settings
    SETTINGS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in the test suite where settings are absent
    SETTINGS_AVAILABLE = False
    settings = None


logger = logging.getLogger(__name__)


class DecisionAgent:
    """Analyzes remediation signals and determines suitable remediation type."""

    def __init__(self, model_name: Optional[str] = None, temperature: Optional[float] = None) -> None:
        if SETTINGS_AVAILABLE and settings:
            self.model_name = model_name or getattr(settings, "ai_model_name", "gpt-3.5-turbo")
            self.temperature = temperature if temperature is not None else getattr(settings, "ai_temperature", 0.1)
            api_key = getattr(settings, "openai_api_key", None)
        else:
            self.model_name = model_name or "gpt-3.5-turbo"
            self.temperature = temperature if temperature is not None else 0.1
            api_key = os.getenv("OPENAI_API_KEY")

        # Provide a harmless default key so unit tests that mock the OpenAI client do not fail.
        self.api_key = api_key or "test-key"

        # Complexity weights reused across helpers
        self.complexity_weights: Dict[str, Dict[Any, float]] = {
            "data_types": {
                DataType.PERSONAL_DATA: 1,
                DataType.SENSITIVE_DATA: 3,
                DataType.FINANCIAL_DATA: 3,
                DataType.HEALTH_DATA: 4,
                DataType.BIOMETRIC_DATA: 5,
                DataType.LOCATION_DATA: 2,
                DataType.BEHAVIORAL_DATA: 2,
            },
            "risk_levels": {
                RiskLevel.LOW: 1,
                RiskLevel.MEDIUM: 2,
                RiskLevel.HIGH: 4,
                RiskLevel.CRITICAL: 5,
            },
        }

    async def make_decision(self, signal: RemediationSignal) -> RemediationDecision:
        """Primary entrypoint used by the remediation graph and unit tests."""

        return await self._evaluate_signal(signal)

    async def analyze_violation(self, signal: RemediationSignal) -> RemediationDecision:
        """Backward compatible alias used by legacy callers."""

        return await self._evaluate_signal(signal)

    async def _evaluate_signal(self, signal: RemediationSignal) -> RemediationDecision:
        factors = self._build_decision_factors(signal)

        try:
            payload = await self._analyze_with_llm(signal, factors)
            if not self._validate_decision_data(payload):
                raise ValueError("LLM payload validation failed")
        except Exception as exc:  # pragma: no cover - behaviour validated via tests
            logger.warning("LLM decision unavailable (%s); using rule-based logic", exc)
            payload = self._determine_rule_based_decision(signal, factors)

        return self._decision_from_payload(signal, payload)

    def _build_decision_factors(self, signal: RemediationSignal) -> Dict[str, Any]:
        actions = signal.violation.remediation_actions or []
        complexity = self._assess_complexity(actions)
        cross_impact = self._estimate_cross_system_impact(signal)

        return {
            "actions": actions,
            "complexity_score": complexity.get("complexity_score", 1.0),
            "automation_patterns": complexity.get("automation_patterns", 0),
            "cross_system_impact": cross_impact,
            "risk_level": signal.violation.risk_level,
        }

    async def _analyze_with_llm(
        self, signal: RemediationSignal, factors: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Request a recommendation from the LLM service."""

        client = openai.AsyncOpenAI(api_key=self.api_key)
        prompt = self._build_prompt(signal, factors or self._build_decision_factors(signal))

        response = await client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI compliance remediation specialist who responds with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:  # pragma: no cover - defensive
            raise ValueError("Malformed response from LLM") from exc

        payload = self._parse_llm_response(content)
        if payload.get("__fallback__"):
            raise ValueError("Failed to parse LLM response")
        return payload

    def _build_prompt(self, signal: RemediationSignal, factors: Dict[str, Any]) -> str:
        variables = self._build_prompt_variables(signal, factors)
        return json.dumps(variables, default=str)

    def _validate_decision_data(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False

        required = {"confidence_score", "reasoning", "estimated_effort", "risk_if_delayed"}
        if not required.issubset(payload.keys()):
            return False

        try:
            confidence = float(payload["confidence_score"])
            estimated_effort = int(payload["estimated_effort"])
        except (TypeError, ValueError):
            return False

        if not 0.0 <= confidence <= 1.0 or estimated_effort < 0:
            return False

        try:
            self._map_string_to_risk_level(str(payload["risk_if_delayed"]))
        except ValueError:
            return False

        remediation_value = payload.get("remediation_type") or payload.get("decision_type")
        if remediation_value is None:
            return False

        remediation_type = str(remediation_value).lower()
        return remediation_type in {choice.value for choice in RemediationType}

    def _assess_complexity(self, actions: Optional[List[str]]) -> Dict[str, Any]:
        if not actions:
            return {"complexity_score": 1.0, "automation_patterns": 0, "average_length": 0.0}

        action_count = len(actions)
        avg_length = sum(len(action) for action in actions) / action_count

        automation_keywords = ("update", "notify", "email", "log", "flag")
        high_risk_keywords = ("delete", "purge", "legal", "regulator", "contract", "policy")

        automation_hits = sum(1 for action in actions if any(keyword in action.lower() for keyword in automation_keywords))
        high_risk_hits = sum(1 for action in actions if any(keyword in action.lower() for keyword in high_risk_keywords))

        complexity_score = min(5.0, 1.0 + action_count * 0.4 + high_risk_hits * 0.6)

        return {
            "complexity_score": round(complexity_score, 2),
            "automation_patterns": automation_hits,
            "high_risk_actions": high_risk_hits,
            "average_length": round(avg_length, 2),
        }

    def _estimate_cross_system_impact(self, signal: RemediationSignal) -> str:
        factors: List[str] = []

        activity = signal.activity
        if activity and activity.cross_border_transfers:
            factors.append("cross-border data flows")
        if activity and activity.automated_decision_making:
            factors.append("automated decision systems")
        if activity and len(activity.recipients) > 2:
            factors.append("multiple data recipients")
        if len(signal.violation.remediation_actions or []) > 3:
            factors.append("multiple remediation steps")

        if len(factors) >= 3:
            return "high"
        if factors:
            return "medium"
        return "low"

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logger.debug("Primary JSON parsing failed for LLM response")

        logger.warning("Falling back to heuristic parsing for LLM response")
        return self._fallback_parse(response)

    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        response_lower = response.lower()
        remediation_type = "human_in_loop"
        if "automatic" in response_lower:
            remediation_type = "automatic"
        elif "manual" in response_lower or "legal" in response_lower:
            remediation_type = "manual_only"

        confidence = 0.6 if "high" in response_lower else 0.5
        estimated_effort = 60 if remediation_type != "automatic" else 30
        risk = "high" if "risk" in response_lower and "high" in response_lower else "medium"

        return {
            "remediation_type": remediation_type,
            "confidence_score": confidence,
            "reasoning": "Could not parse structured response; defaulting to conservative remediation.",
            "estimated_effort": estimated_effort,
            "risk_if_delayed": risk,
            "prerequisites": ["Manual review required"] if remediation_type != "automatic" else [],
            "__fallback__": True,
        }

    def _create_fallback_decision(self, signal: RemediationSignal) -> RemediationDecision:
        payload = self._determine_rule_based_decision(signal, self._build_decision_factors(signal))
        return self._decision_from_payload(signal, payload)

    def _determine_rule_based_decision(
        self, signal: RemediationSignal, factors: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        factors = factors or self._build_decision_factors(signal)
        risk_level: RiskLevel = factors.get("risk_level", RiskLevel.MEDIUM)
        complexity_score = float(factors.get("complexity_score", 1.0))
        automation_patterns = factors.get("automation_patterns", 0)
        cross_system_impact = factors.get("cross_system_impact", "low")

        actions = factors.get("actions", signal.violation.remediation_actions or [])
        contains_deletion = any("delete" in action.lower() for action in actions)
        contains_policy = any("policy" in action.lower() for action in actions)

        if risk_level == RiskLevel.CRITICAL or contains_policy:
            decision_type = RemediationType.MANUAL_ONLY
        elif risk_level == RiskLevel.HIGH or contains_deletion or cross_system_impact == "high":
            decision_type = RemediationType.HUMAN_IN_LOOP
        elif len(actions) >= 3 or cross_system_impact == "medium":
            decision_type = RemediationType.HUMAN_IN_LOOP
        else:
            decision_type = RemediationType.AUTOMATIC

        confidence = self._calculate_confidence_score(
            {
                "risk_level": risk_level,
                "complexity_score": complexity_score,
                "automation_patterns": automation_patterns,
            }
        )
        estimated_effort = self._estimate_effort(actions, complexity_score)
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

    def _decision_from_payload(self, signal: RemediationSignal, payload: Dict[str, Any]) -> RemediationDecision:
        remediation_value = payload.get("decision_type") or payload.get("remediation_type")
        remediation_type = RemediationType(str(remediation_value).lower())
        risk_level = self._map_string_to_risk_level(str(payload.get("risk_if_delayed", "medium")))

        return RemediationDecision(
            violation_id=signal.violation.rule_id,
            activity_id=getattr(signal.activity, "id", None),
            remediation_type=remediation_type,
            decision_type=remediation_type,
            confidence_score=float(payload.get("confidence_score", 0.7)),
            reasoning=str(payload.get("reasoning", "No reasoning provided")),
            estimated_effort=int(payload.get("estimated_effort", 60)),
            risk_if_delayed=risk_level,
            prerequisites=list(payload.get("prerequisites", [])),
            recommended_actions=list(payload.get("recommended_actions", [])),
        )

    def _determine_prerequisites(
        self, signal: RemediationSignal, remediation_type: RemediationType
    ) -> List[str]:
        prerequisites: List[str] = []

        if remediation_type == RemediationType.MANUAL_ONLY:
            prerequisites.extend([
                "Legal review required",
                "Compliance officer approval",
                "Impact assessment",
            ])
        elif remediation_type == RemediationType.HUMAN_IN_LOOP:
            prerequisites.extend([
                "Human review and approval",
                "Backup and recovery plan",
            ])

        if getattr(signal.activity, "cross_border_transfers", False):
            prerequisites.append("Cross-border transfer compliance check")

        if signal.violation.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            prerequisites.append("Risk assessment documentation")

        if "delete" in signal.violation.rule_id.lower():
            prerequisites.append("Data retention policy compliance")

        return prerequisites

    def get_decision_criteria(self) -> Dict[str, Any]:  # pragma: no cover - exercised via unit tests
        return {
            "automatic_thresholds": {
                "max_risk_level": "medium",
                "max_complexity": 2.5,
                "required_confidence": 0.8,
            },
            "human_loop_thresholds": {
                "max_risk_level": "high",
                "required_confidence": 0.6,
            },
            "complexity_weights": self.complexity_weights,
        }

    def _map_risk_level_to_string(self, risk: RiskLevel) -> str:
        return risk.value

    def _map_string_to_risk_level(self, value: str) -> RiskLevel:
        try:
            return RiskLevel(value.lower())
        except ValueError:
            logger.warning(f"Invalid risk level '{value}', defaulting to MEDIUM")
            return RiskLevel.MEDIUM

    def _calculate_confidence_score(self, factors: Dict[str, Any]) -> float:
        risk = factors.get("risk_level", RiskLevel.MEDIUM)
        complexity = float(factors.get("complexity_score", 1.0))
        automation_hits = int(factors.get("automation_patterns", 0))

        base = 0.75 if risk in {RiskLevel.LOW, RiskLevel.MEDIUM} else 0.6
        adjustment = 0.05 * automation_hits
        penalty = 0.06 * max(0.0, complexity - 2.0)

        score = max(0.2, min(0.95, base + adjustment - penalty))
        return round(score, 2)

    def _estimate_effort(self, actions: List[str], complexity_score: float) -> int:
        count = max(1, len(actions))
        base_effort = 20 * count
        multiplier = 1 + (complexity_score / 4)
        return int(base_effort * multiplier)

    def _get_decision_rationale(self, decision_type: str, factors: Dict[str, Any]) -> str:
        risk = factors.get("risk_level", RiskLevel.MEDIUM)
        complexity = factors.get("complexity_score", 1.0)
        impact = factors.get("cross_system_impact", "low")

        fragments = [
            f"Risk level {risk.value}",
            f"complexity score {complexity}",
            f"cross-system impact {impact}",
        ]

        if decision_type == RemediationType.AUTOMATIC.value:
            fragments.append("suitable for automated execution")
        elif decision_type == RemediationType.HUMAN_IN_LOOP.value:
            fragments.append("requires human verification before completion")
        else:
            fragments.append("requires dedicated manual handling")

        return "; ".join(fragments)

    def _build_prompt_variables(self, signal: RemediationSignal, factors: Dict[str, Any]) -> Dict[str, Any]:
        activity = signal.activity
        return {
            "violation_id": signal.violation.rule_id,
            "violation_description": signal.violation.description,
            "risk_level": signal.violation.risk_level.value,
            "remediation_actions": signal.violation.remediation_actions or [],
            "activity": {
                "purpose": getattr(activity, "purpose", "unspecified"),
                "data_types": [dt.value for dt in getattr(activity, "data_types", [])],
                "legal_bases": getattr(activity, "legal_bases", []),
                "cross_border": getattr(activity, "cross_border_transfers", False),
                "automated_decisions": getattr(activity, "automated_decision_making", False),
            },
            "complexity": factors.get("complexity_score", 1.0),
            "automation_patterns": factors.get("automation_patterns", 0),
            "cross_system_impact": factors.get("cross_system_impact", "low"),
            "context": signal.context,
        }
