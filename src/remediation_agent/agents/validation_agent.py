"""
Validation Agent for remediation feasibility assessment

This agent validates whether proposed remediation actions can actually be
executed automatically and identifies any blockers or prerequisites.
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from ..state.models import (
    RemediationSignal,
    RemediationDecision,
    RemediationType,
    WorkflowStep
)
from src.compliance_agent.models.compliance_models import ComplianceViolation

logger = logging.getLogger(__name__)


class ValidationAgent:
    """
    Agent responsible for validating the feasibility of automatic remediation
    and identifying potential blockers or prerequisites.
    """

    def __init__(self):
        # Known automation patterns and their feasibility
        self.automation_patterns = {
            "data_retention": {
                "keywords": ["retention", "delete", "purge", "archive"],
                "feasibility": 0.9,
                "prerequisites": ["data_location_known", "backup_verified"],
                "risk_factors": ["active_processing", "legal_hold"]
            },
            "consent_management": {
                "keywords": ["consent", "withdraw", "opt-out", "unsubscribe"],
                "feasibility": 0.8,
                "prerequisites": ["consent_system_available", "user_identified"],
                "risk_factors": ["legal_basis_change", "legitimate_interest"]
            },
            "data_portability": {
                "keywords": ["export", "download", "portability", "transfer"],
                "feasibility": 0.7,
                "prerequisites": ["data_format_defined", "export_mechanism"],
                "risk_factors": ["third_party_data", "security_clearance"]
            },
            "access_control": {
                "keywords": ["access", "permission", "role", "authorization"],
                "feasibility": 0.8,
                "prerequisites": ["identity_verified", "role_defined"],
                "risk_factors": ["system_dependencies", "business_impact"]
            },
            "data_minimization": {
                "keywords": ["minimize", "reduce", "limit", "necessary"],
                "feasibility": 0.6,
                "prerequisites": ["data_usage_analysis", "business_approval"],
                "risk_factors": ["operational_impact", "data_dependencies"]
            },
            "encryption": {
                "keywords": ["encrypt", "protection", "secure", "hash"],
                "feasibility": 0.9,
                "prerequisites": ["encryption_key_available", "system_downtime"],
                "risk_factors": ["performance_impact", "key_management"]
            },
            "anonymization": {
                "keywords": ["anonymize", "pseudonymize", "de-identify"],
                "feasibility": 0.5,
                "prerequisites": ["anonymization_method", "re-identification_risk"],
                "risk_factors": ["data_utility", "linkage_attacks"]
            }
        }

        # System integration complexity factors
        self.integration_factors = {
            "database_operations": 0.8,
            "api_integrations": 0.7,
            "file_system_changes": 0.9,
            "third_party_services": 0.4,
            "manual_processes": 0.1,
            "regulatory_filings": 0.2
        }

    async def validate_decision(self, decision: RemediationDecision) -> 'ValidationResult':
        """
        Validate a remediation decision
        
        Args:
            decision: The remediation decision to validate
            
        Returns:
            ValidationResult with status and details
        """
        from ..state.models import ValidationResult, ValidationStatus
        
        try:
            errors = []
            warnings = []
            recommendations = []
            
            # Check confidence score
            if decision.confidence_score < 0.3:
                errors.append("Decision confidence too low")
            elif decision.confidence_score < 0.6:
                warnings.append("Low decision confidence")
                
            # Check estimated effort
            if decision.estimated_effort > 480:  # 8 hours
                warnings.append("High estimated effort")
                
            # Determine status
            if errors:
                status = ValidationStatus.INVALID
                confidence = 0.3
            elif warnings:
                status = ValidationStatus.WARNING
                confidence = 0.7
            else:
                status = ValidationStatus.VALID
                confidence = 0.9
                
            return ValidationResult(
                status=status,
                confidence_score=confidence,
                validation_errors=errors,
                warnings=warnings,
                recommendations=recommendations,
                details={"decision_type": decision.remediation_type.value}
            )
            
        except Exception as e:
            logger.error(f"Error validating decision: {str(e)}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence_score=0.1,
                validation_errors=[f"Validation error: {str(e)}"],
                warnings=[],
                recommendations=[],
                details={}
            )

    async def validate_remediation_feasibility(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Validate the feasibility of executing the proposed remediation

        Args:
            signal: The remediation signal
            decision: The proposed remediation decision

        Returns:
            Tuple of (feasibility_score, validation_details)
        """
        logger.info(f"Validating remediation feasibility for {signal.violation.rule_id}")

        try:
            # Analyze remediation actions
            action_analysis = self._analyze_remediation_actions(
                signal.violation.remediation_actions
            )

            # Check system capabilities
            system_check = self._check_system_capabilities(signal)

            # Assess integration complexity
            integration_analysis = self._analyze_integration_complexity(signal)

            # Calculate overall feasibility score
            feasibility_score = self._calculate_feasibility_score(
                action_analysis,
                system_check,
                integration_analysis,
                decision
            )

            # Compile validation details
            validation_details = {
                "action_analysis": action_analysis,
                "system_capabilities": system_check,
                "integration_complexity": integration_analysis,
                "feasibility_score": feasibility_score,
                "blockers": self._identify_blockers(action_analysis, system_check),
                "prerequisites": self._compile_prerequisites(action_analysis),
                "risk_factors": self._identify_risk_factors(action_analysis, signal),
                "recommended_adjustments": self._recommend_adjustments(
                    feasibility_score, decision.remediation_type
                )
            }

            logger.info(f"Feasibility validation complete: score={feasibility_score}")
            return feasibility_score, validation_details

        except Exception as e:
            logger.error(f"Error validating remediation feasibility: {str(e)}")
            return 0.1, {"error": str(e), "fallback": True}

    def _analyze_remediation_actions(self, actions: List[str]) -> Dict[str, Any]:
        """Analyze each remediation action for automation potential"""
        action_details = []
        total_feasibility = 0.0

        for action in actions:
            action_lower = action.lower()
            matched_patterns = []

            # Find matching automation patterns
            for pattern_name, pattern_data in self.automation_patterns.items():
                if any(keyword in action_lower for keyword in pattern_data["keywords"]):
                    matched_patterns.append({
                        "pattern": pattern_name,
                        "feasibility": pattern_data["feasibility"],
                        "prerequisites": pattern_data["prerequisites"],
                        "risk_factors": pattern_data["risk_factors"]
                    })

            # Calculate action feasibility
            if matched_patterns:
                action_feasibility = max(p["feasibility"] for p in matched_patterns)
            else:
                action_feasibility = 0.3  # Unknown actions get low feasibility

            action_details.append({
                "action": action,
                "feasibility": action_feasibility,
                "matched_patterns": matched_patterns,
                "classification": self._classify_action_type(action)
            })

            total_feasibility += action_feasibility

        avg_feasibility = total_feasibility / len(actions) if actions else 0.0

        return {
            "actions": action_details,
            "average_feasibility": avg_feasibility,
            "total_actions": len(actions),
            "high_feasibility_count": len([a for a in action_details if a["feasibility"] > 0.7]),
            "automation_patterns_found": len(set(
                p["pattern"] for a in action_details for p in a["matched_patterns"]
            ))
        }

    def _check_system_capabilities(self, signal: RemediationSignal) -> Dict[str, Any]:
        """Check available system capabilities for remediation"""
        # This would integrate with actual system inventory in production
        capabilities = {
            "database_access": True,
            "api_endpoints": True,
            "file_system_access": True,
            "encryption_tools": True,
            "backup_systems": True,
            "audit_logging": True,
            "notification_system": True,
            "workflow_engine": True
        }

        # Assess data-specific capabilities
        data_capabilities = {}
        for data_type in signal.activity.data_types:
            data_capabilities[data_type.value] = {
                "location_known": True,
                "access_methods": ["api", "database"],
                "backup_available": True,
                "encryption_status": "encrypted"
            }

        return {
            "general_capabilities": capabilities,
            "data_specific": data_capabilities,
            "missing_capabilities": [],
            "capability_score": 0.85  # Would be calculated based on actual checks
        }

    def _analyze_integration_complexity(self, signal: RemediationSignal) -> Dict[str, Any]:
        """Analyze the complexity of integrating remediation actions"""
        complexity_factors = []

        # Check cross-border implications
        if signal.activity.cross_border_transfers:
            complexity_factors.append({
                "factor": "cross_border_transfers",
                "complexity": 0.6,
                "impact": "Requires coordination across jurisdictions"
            })

        # Check automated decision making impact
        if signal.activity.automated_decision_making:
            complexity_factors.append({
                "factor": "automated_decisions",
                "complexity": 0.7,
                "impact": "May affect ML models and decision processes"
            })

        # Check number of recipients
        if len(signal.activity.recipients) > 2:
            complexity_factors.append({
                "factor": "multiple_recipients",
                "complexity": 0.5,
                "impact": f"Requires coordination with {len(signal.activity.recipients)} recipients"
            })

        # Calculate overall complexity
        if complexity_factors:
            avg_complexity = sum(f["complexity"] for f in complexity_factors) / len(complexity_factors)
        else:
            avg_complexity = 0.2  # Low complexity if no special factors

        return {
            "factors": complexity_factors,
            "average_complexity": avg_complexity,
            "integration_score": 1.0 - avg_complexity,  # Higher score = lower complexity
            "estimated_integration_time": self._estimate_integration_time(complexity_factors)
        }

    def _calculate_feasibility_score(
        self,
        action_analysis: Dict[str, Any],
        system_check: Dict[str, Any],
        integration_analysis: Dict[str, Any],
        decision: RemediationDecision
    ) -> float:
        """Calculate overall feasibility score"""
        # Weight the different factors
        action_weight = 0.4
        system_weight = 0.3
        integration_weight = 0.3

        feasibility = (
            action_analysis["average_feasibility"] * action_weight +
            system_check["capability_score"] * system_weight +
            integration_analysis["integration_score"] * integration_weight
        )

        # Apply confidence penalty if decision confidence is low
        if decision.confidence_score < 0.7:
            feasibility *= 0.8

        return min(1.0, max(0.0, feasibility))

    def _identify_blockers(
        self,
        action_analysis: Dict[str, Any],
        system_check: Dict[str, Any]
    ) -> List[str]:
        """Identify potential blockers to automatic remediation"""
        blockers = []

        # Check for low-feasibility actions
        for action_detail in action_analysis["actions"]:
            if action_detail["feasibility"] < 0.4:
                blockers.append(f"Low automation potential for: {action_detail['action']}")

        # Check for missing system capabilities
        for capability, available in system_check["general_capabilities"].items():
            if not available:
                blockers.append(f"Missing system capability: {capability}")

        # Add pattern-specific blockers
        for action_detail in action_analysis["actions"]:
            for pattern in action_detail["matched_patterns"]:
                for risk_factor in pattern["risk_factors"]:
                    blockers.append(f"Risk factor for {action_detail['action']}: {risk_factor}")

        return blockers

    def _compile_prerequisites(self, action_analysis: Dict[str, Any]) -> List[str]:
        """Compile all prerequisites for remediation"""
        all_prerequisites = []

        for action_detail in action_analysis["actions"]:
            for pattern in action_detail["matched_patterns"]:
                all_prerequisites.extend(pattern["prerequisites"])

        # Remove duplicates while preserving order
        return list(dict.fromkeys(all_prerequisites))

    def _identify_risk_factors(
        self,
        action_analysis: Dict[str, Any],
        signal: RemediationSignal
    ) -> List[str]:
        """Identify risk factors for automatic remediation"""
        risk_factors = []

        # High-risk data types
        high_risk_data = ["health_data", "biometric_data", "financial_data"]
        for data_type in signal.activity.data_types:
            if data_type.value in high_risk_data:
                risk_factors.append(f"High-risk data type: {data_type.value}")

        # Cross-border transfers
        if signal.activity.cross_border_transfers:
            risk_factors.append("Cross-border data transfers present")

        # Multiple remediation actions
        if len(signal.violation.remediation_actions) > 3:
            risk_factors.append("Multiple complex remediation actions required")

        return risk_factors

    def _recommend_adjustments(
        self,
        feasibility_score: float,
        current_type: RemediationType
    ) -> List[str]:
        """Recommend adjustments based on feasibility analysis"""
        recommendations = []

        if feasibility_score < 0.4 and current_type == RemediationType.AUTOMATIC:
            recommendations.append("Consider changing to HUMAN_IN_LOOP due to low feasibility")

        if feasibility_score > 0.8 and current_type == RemediationType.MANUAL_ONLY:
            recommendations.append("Consider AUTOMATIC remediation due to high feasibility")

        if 0.4 <= feasibility_score <= 0.7:
            recommendations.append("HUMAN_IN_LOOP approach recommended for oversight")

        if feasibility_score < 0.6:
            recommendations.append("Implement additional validation steps")
            recommendations.append("Consider phased approach with manual verification")

        return recommendations

    def _classify_action_type(self, action: str) -> str:
        """Classify the type of remediation action"""
        action_lower = action.lower()

        if any(word in action_lower for word in ["delete", "remove", "purge"]):
            return "deletion"
        elif any(word in action_lower for word in ["update", "modify", "change"]):
            return "modification"
        elif any(word in action_lower for word in ["encrypt", "secure", "protect"]):
            return "protection"
        elif any(word in action_lower for word in ["notify", "inform", "contact"]):
            return "notification"
        elif any(word in action_lower for word in ["transfer", "export", "migrate"]):
            return "transfer"
        else:
            return "other"

    def _estimate_integration_time(self, complexity_factors: List[Dict[str, Any]]) -> int:
        """Estimate integration time in minutes"""
        base_time = 30  # Base automation setup time

        for factor in complexity_factors:
            if factor["complexity"] > 0.7:
                base_time += 60  # High complexity adds 1 hour
            elif factor["complexity"] > 0.4:
                base_time += 30  # Medium complexity adds 30 minutes
            else:
                base_time += 10  # Low complexity adds 10 minutes

        return min(base_time, 480)  # Cap at 8 hours
        
    def assess_feasibility(self, actions: List[str], signal: RemediationSignal) -> Dict[str, Any]:
        """Assess feasibility of remediation actions"""
        try:
            action_analysis = self._analyze_remediation_actions(actions)
            system_check = self._check_system_capabilities(signal)
            
            feasibility_score = 0.0
            for action in actions:
                action_type = self._classify_action_type(action)
                pattern_match = self._match_automation_pattern(action)
                if pattern_match:
                    feasibility_score += pattern_match.get('feasibility', 0.5)
                else:
                    feasibility_score += 0.3
                    
            feasibility_score = feasibility_score / len(actions) if actions else 0.1
            
            return {
                "feasibility_score": feasibility_score,
                "action_analysis": action_analysis,
                "system_capabilities": system_check,
                "automation_potential": feasibility_score > 0.6
            }
        except Exception as e:
            logger.error(f"Error assessing feasibility: {str(e)}")
            return {"feasibility_score": 0.1, "error": str(e)}
            
    def _match_automation_pattern(self, action: str) -> Dict[str, Any]:
        """Match action against automation patterns"""
        action_lower = action.lower()
        for pattern_name, pattern_data in self.automation_patterns.items():
            for keyword in pattern_data['keywords']:
                if keyword in action_lower:
                    return pattern_data
        return {}
        
    def validate_workflow(self, workflow) -> 'ValidationResult':
        """Validate a workflow"""
        from ..state.models import ValidationResult, ValidationStatus
        
        try:
            errors = []
            warnings = []
            
            if not hasattr(workflow, 'steps') or not workflow.steps:
                errors.append("Workflow has no steps")
                
            if errors:
                status = ValidationStatus.INVALID
            else:
                status = ValidationStatus.VALID
                
            return ValidationResult(
                status=status,
                confidence_score=0.8 if status == ValidationStatus.VALID else 0.2,
                validation_errors=errors,
                warnings=warnings,
                recommendations=[],
                details={}
            )
        except Exception as e:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence_score=0.1,
                validation_errors=[str(e)],
                warnings=[],
                recommendations=[],
                details={}
            )
            
    def _calculate_validation_confidence(self, factors: Dict[str, Any]) -> float:
        """Calculate validation confidence"""
        try:
            base_confidence = 0.7
            
            if 'feasibility_score' in factors:
                base_confidence += (factors['feasibility_score'] - 0.5) * 0.4
                
            if 'complexity' in factors:
                base_confidence -= factors['complexity'] * 0.2
                
            return max(0.1, min(1.0, base_confidence))
        except Exception:
            return 0.5
            
    def _validate_step_parameters(self, step) -> Dict[str, Any]:
        """Validate step parameters"""
        try:
            errors = []
            warnings = []
            
            if not hasattr(step, 'parameters') or not step.parameters:
                errors.append("Step missing parameters")
                
            if hasattr(step, 'action_type'):
                if step.action_type == 'api_call' and 'endpoint' not in step.parameters:
                    errors.append("API call missing endpoint parameter")
                elif step.action_type == 'database_operation' and 'query' not in step.parameters:
                    errors.append("Database operation missing query parameter")
                    
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
        except Exception as e:
            return {"valid": False, "errors": [str(e)], "warnings": []}
            
    def _estimate_workflow_risk(self, workflow) -> float:
        """Estimate workflow risk level"""
        try:
            base_risk = 0.3
            
            if hasattr(workflow, 'steps'):
                # Higher risk for more steps
                base_risk += len(workflow.steps) * 0.05
                
                # Check for risky operations
                for step in workflow.steps:
                    if hasattr(step, 'action_type'):
                        if step.action_type in ['database_operation', 'data_deletion']:
                            base_risk += 0.2
                            
            return min(1.0, base_risk)
        except Exception:
            return 0.5