"""
Remediation Validator Tool

This tool provides validation capabilities for remediation actions,
ensuring they can be safely executed and meet compliance requirements.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import asyncio

from ..state.models import (
    RemediationSignal,
    RemediationDecision,
    WorkflowStep,
    RemediationType
)
from src.compliance_agent.models.compliance_models import (
    DataType,
    RiskLevel,
    ComplianceViolation
)

logger = logging.getLogger(__name__)


class RemediationValidator:
    """
    Tool for validating remediation actions before execution
    """

    def __init__(self):
        # Validation rules for different data types
        self.data_type_rules = {
            DataType.PERSONAL_DATA: {
                "encryption_required": True,
                "backup_required": True,
                "audit_trail": True,
                "retention_check": True,
                "cross_border_restrictions": True
            },
            DataType.SENSITIVE_DATA: {
                "encryption_required": True,
                "backup_required": True,
                "audit_trail": True,
                "retention_check": True,
                "special_handling": True,
                "access_logging": True
            },
            DataType.HEALTH_DATA: {
                "encryption_required": True,
                "backup_required": True,
                "audit_trail": True,
                "retention_check": True,
                "hipaa_compliance": True,
                "access_logging": True,
                "anonymization_check": True
            },
            DataType.FINANCIAL_DATA: {
                "encryption_required": True,
                "backup_required": True,
                "audit_trail": True,
                "retention_check": True,
                "pci_compliance": True,
                "fraud_check": True
            },
            DataType.BIOMETRIC_DATA: {
                "encryption_required": True,
                "backup_required": True,
                "audit_trail": True,
                "retention_check": True,
                "special_handling": True,
                "irreversible_deletion": True
            }
        }

        # Risk level validation requirements
        self.risk_level_requirements = {
            RiskLevel.CRITICAL: {
                "manual_approval": True,
                "dual_authorization": True,
                "immediate_execution": True,
                "full_audit": True,
                "notification_required": True
            },
            RiskLevel.HIGH: {
                "manual_approval": True,
                "full_audit": True,
                "notification_required": True,
                "verification_required": True
            },
            RiskLevel.MEDIUM: {
                "audit_trail": True,
                "notification_recommended": True,
                "verification_recommended": True
            },
            RiskLevel.LOW: {
                "basic_logging": True
            }
        }

    async def validate_remediation_plan(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision,
        workflow_steps: List[WorkflowStep]
    ) -> Dict[str, Any]:
        """
        Validate a complete remediation plan

        Args:
            signal: The remediation signal
            decision: The remediation decision
            workflow_steps: Planned workflow steps

        Returns:
            Validation result with pass/fail and detailed findings
        """
        logger.info(f"Validating remediation plan for {signal.violation.rule_id}")

        validation_results = {
            "overall_valid": True,
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_validation": {},
            "decision_validation": {},
            "workflow_validation": {},
            "data_validation": {},
            "compliance_validation": {},
            "security_validation": {},
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        try:
            # Validate the signal
            signal_results = await self._validate_signal(signal)
            validation_results["signal_validation"] = signal_results

            # Validate the decision
            decision_results = await self._validate_decision(signal, decision)
            validation_results["decision_validation"] = decision_results

            # Validate workflow steps
            workflow_results = await self._validate_workflow_steps(signal, workflow_steps)
            validation_results["workflow_validation"] = workflow_results

            # Validate data handling requirements
            data_results = await self._validate_data_handling(signal, decision)
            validation_results["data_validation"] = data_results

            # Validate compliance requirements
            compliance_results = await self._validate_compliance_requirements(signal, decision)
            validation_results["compliance_validation"] = compliance_results

            # Validate security requirements
            security_results = await self._validate_security_requirements(signal, decision)
            validation_results["security_validation"] = security_results

            # Compile overall results
            all_results = [
                signal_results, decision_results, workflow_results,
                data_results, compliance_results, security_results
            ]

            validation_results["overall_valid"] = all(r.get("valid", False) for r in all_results)

            # Collect warnings and errors
            for result in all_results:
                validation_results["warnings"].extend(result.get("warnings", []))
                validation_results["errors"].extend(result.get("errors", []))
                validation_results["recommendations"].extend(result.get("recommendations", []))

            logger.info(f"Validation complete: {'PASS' if validation_results['overall_valid'] else 'FAIL'}")

            return validation_results

        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            validation_results["overall_valid"] = False
            validation_results["errors"].append(f"Validation error: {str(e)}")
            return validation_results
            
    def _check_database_state(self, user_id: str) -> Dict[str, Any]:
        """Check database state for user"""
        try:
            # Mock database check - in real implementation would check actual DB
            return {
                "valid": True,
                "user_exists": True,
                "confidence": 0.9
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "confidence": 0.1
            }
            
    async def _verify_system_availability(self, system_name: str) -> Dict[str, Any]:
        """Verify system availability"""
        try:
            # Mock system check - in real implementation would ping actual systems
            return {
                "available": True,
                "response_time": 50,
                "confidence": 0.9
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "confidence": 0.1
            }
            
    def _check_data_relationships(self, user_id: str) -> Dict[str, Any]:
        """Check data relationships"""
        try:
            # Mock relationship check
            return {
                "valid": True,
                "orphaned_records": 0,
                "confidence": 0.9
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "confidence": 0.1
            }
            
    def _verify_backup_exists(self, table_name: str) -> Dict[str, Any]:
        """Verify backup exists"""
        try:
            # Mock backup check
            return {
                "exists": True,
                "backup_id": "backup-123",
                "confidence": 0.9
            }
        except Exception as e:
            return {
                "exists": False,
                "error": str(e),
                "confidence": 0.1
            }
            
    def _calculate_validation_score(self, checks: Dict[str, Any]) -> float:
        """Calculate overall validation score"""
        try:
            scores = []
            for check_name, check_result in checks.items():
                if isinstance(check_result, dict):
                    if 'confidence' in check_result:
                        scores.append(check_result['confidence'])
                    elif 'valid' in check_result:
                        scores.append(0.9 if check_result['valid'] else 0.1)
                    elif 'available' in check_result:
                        scores.append(0.9 if check_result['available'] else 0.1)
            
            return sum(scores) / len(scores) if scores else 0.5
        except Exception:
            return 0.1

    async def _validate_signal(self, signal: RemediationSignal) -> Dict[str, Any]:
        """Validate the remediation signal"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Check signal completeness
        if not signal.violation.remediation_actions:
            results["errors"].append("No remediation actions specified in violation")
            results["valid"] = False

        if not signal.activity.data_types:
            results["warnings"].append("No data types specified in activity")

        # Check urgency vs risk level alignment
        if signal.urgency != signal.violation.risk_level:
            results["warnings"].append(
                f"Signal urgency ({signal.urgency}) doesn't match violation risk level ({signal.violation.risk_level})"
            )

        # Check for stale signals
        signal_age = (datetime.now(timezone.utc) - signal.received_at).total_seconds() / 3600
        if signal_age > 24:
            results["warnings"].append(f"Signal is {signal_age:.1f} hours old")

        return results

    async def _validate_decision(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate the remediation decision"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Check decision confidence
        if decision.confidence_score < 0.6:
            results["warnings"].append(f"Low decision confidence: {decision.confidence_score}")

        if decision.confidence_score < 0.3:
            results["errors"].append("Decision confidence too low for automatic execution")
            results["valid"] = False

        # Validate decision type based on risk level
        risk_requirements = self.risk_level_requirements.get(signal.violation.risk_level, {})

        if signal.violation.risk_level == RiskLevel.CRITICAL:
            if decision.remediation_type == RemediationType.AUTOMATIC:
                results["errors"].append("Critical risk violations should not be fully automatic")
                results["valid"] = False

        # Check estimated effort reasonableness
        if decision.estimated_effort > 480:  # 8 hours
            results["warnings"].append(f"High estimated effort: {decision.estimated_effort} minutes")

        # Validate prerequisites
        if decision.remediation_type == RemediationType.AUTOMATIC and len(decision.prerequisites) > 5:
            results["warnings"].append("Many prerequisites for automatic remediation")

        return results

    async def _validate_workflow_steps(
        self,
        signal: RemediationSignal,
        steps: List[WorkflowStep]
    ) -> Dict[str, Any]:
        """Validate workflow steps"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        if not steps:
            results["errors"].append("No workflow steps defined")
            results["valid"] = False
            return results

        # Check for required steps based on data types
        required_steps = set()
        for data_type in signal.activity.data_types:
            rules = self.data_type_rules.get(data_type, {})
            if rules.get("backup_required"):
                required_steps.add("backup_verification")
            if rules.get("audit_trail"):
                required_steps.add("audit_logging")

        step_types = {step.action_type for step in steps}

        # Check for missing required steps
        missing_steps = required_steps - step_types
        if missing_steps:
            results["warnings"].append(f"Missing recommended steps: {missing_steps}")

        # Validate step sequence
        step_sequence_issues = self._validate_step_sequence(steps)
        if step_sequence_issues:
            results["warnings"].extend(step_sequence_issues)

        # Check for risky step combinations
        risky_combinations = self._check_risky_step_combinations(steps)
        if risky_combinations:
            results["warnings"].extend(risky_combinations)

        return results

    async def _validate_data_handling(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate data handling requirements"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        for data_type in signal.activity.data_types:
            rules = self.data_type_rules.get(data_type, {})

            # Check encryption requirements
            if rules.get("encryption_required"):
                if "encrypt" not in " ".join(signal.violation.remediation_actions).lower():
                    results["warnings"].append(f"Encryption recommended for {data_type.value}")

            # Check backup requirements
            if rules.get("backup_required"):
                if "backup" not in " ".join(signal.violation.remediation_actions).lower():
                    results["recommendations"].append(f"Verify backup exists for {data_type.value}")

            # Special handling for sensitive data
            if rules.get("special_handling"):
                if decision.remediation_type == RemediationType.AUTOMATIC:
                    results["warnings"].append(f"Automatic handling of {data_type.value} requires extra caution")

        # Cross-border data handling
        if signal.activity.cross_border_transfers:
            results["warnings"].append("Cross-border transfers require additional validation")

        return results

    async def _validate_compliance_requirements(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate compliance requirements"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Framework-specific validations
        if signal.framework == "gdpr_eu":
            gdpr_validation = self._validate_gdpr_requirements(signal, decision)
            results["warnings"].extend(gdpr_validation.get("warnings", []))
            results["errors"].extend(gdpr_validation.get("errors", []))

        elif signal.framework == "pdpa_singapore":
            pdpa_validation = self._validate_pdpa_requirements(signal, decision)
            results["warnings"].extend(pdpa_validation.get("warnings", []))
            results["errors"].extend(pdpa_validation.get("errors", []))

        # General compliance checks
        if signal.violation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            if decision.remediation_type == RemediationType.AUTOMATIC:
                results["warnings"].append("High-risk violations may require regulatory notification")

        return results

    async def _validate_security_requirements(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate security requirements"""
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Check for security-sensitive operations
        sensitive_actions = ["delete", "purge", "transfer", "export"]
        for action in signal.violation.remediation_actions:
            if any(keyword in action.lower() for keyword in sensitive_actions):
                results["recommendations"].append(f"Security review recommended for: {action}")

        # Validate access controls
        if signal.activity.automated_decision_making:
            results["warnings"].append("Automated decision systems affected - review ML model impact")

        # Check for reversibility
        irreversible_actions = ["delete", "purge", "anonymize"]
        for action in signal.violation.remediation_actions:
            if any(keyword in action.lower() for keyword in irreversible_actions):
                results["recommendations"].append(f"Ensure backup exists before: {action}")

        return results

    def _validate_gdpr_requirements(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate GDPR-specific requirements"""
        results = {"warnings": [], "errors": []}

        # Article 17 - Right to erasure
        if "delete" in " ".join(signal.violation.remediation_actions).lower():
            results["warnings"].append("GDPR deletion requires verification of legal bases")

        # Article 20 - Data portability
        if "export" in " ".join(signal.violation.remediation_actions).lower():
            results["warnings"].append("GDPR data export must be in structured, machine-readable format")

        return results

    def _validate_pdpa_requirements(
        self,
        signal: RemediationSignal,
        decision: RemediationDecision
    ) -> Dict[str, Any]:
        """Validate PDPA Singapore-specific requirements"""
        results = {"warnings": [], "errors": []}

        # PDPA consent withdrawal
        if "consent" in " ".join(signal.violation.remediation_actions).lower():
            results["warnings"].append("PDPA consent withdrawal requires notification to data subject")

        return results

    def _validate_step_sequence(self, steps: List[WorkflowStep]) -> List[str]:
        """Validate the sequence of workflow steps"""
        issues = []

        # Check if backup/verification steps come before destructive actions
        destructive_actions = {"data_deletion", "data_modification", "data_transfer"}
        verification_actions = {"verify_completion", "backup_verification"}

        destructive_indices = [
            i for i, step in enumerate(steps)
            if step.action_type in destructive_actions
        ]

        verification_indices = [
            i for i, step in enumerate(steps)
            if step.action_type in verification_actions
        ]

        for dest_idx in destructive_indices:
            if not any(ver_idx > dest_idx for ver_idx in verification_indices):
                issues.append(f"No verification step after destructive action: {steps[dest_idx].name}")

        return issues

    def _check_risky_step_combinations(self, steps: List[WorkflowStep]) -> List[str]:
        """Check for risky step combinations"""
        warnings = []

        step_types = [step.action_type for step in steps]

        # Check for multiple destructive actions
        destructive_count = sum(1 for action_type in step_types
                              if action_type in {"data_deletion", "data_modification"})

        if destructive_count > 2:
            warnings.append(f"Multiple destructive actions in workflow: {destructive_count}")

        # Check for automation without human oversight
        has_human_step = any(action_type in {"human_review", "human_approval"}
                           for action_type in step_types)

        has_destructive = any(action_type in {"data_deletion", "data_modification"}
                            for action_type in step_types)

        if has_destructive and not has_human_step:
            warnings.append("Destructive actions without human oversight")

        return warnings

    async def validate_execution_readiness(
        self,
        workflow_step: WorkflowStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate if a specific step is ready for execution

        Args:
            workflow_step: The step to validate
            context: Execution context

        Returns:
            Validation result for step execution
        """
        results = {
            "ready_for_execution": True,
            "blockers": [],
            "warnings": [],
            "prerequisites_met": {},
            "estimated_risk": "low"
        }

        # Check step prerequisites
        prerequisites = workflow_step.parameters.get("prerequisites", [])
        for prereq in prerequisites:
            met = await self._check_prerequisite(prereq, context)
            results["prerequisites_met"][prereq] = met
            if not met:
                results["blockers"].append(f"Prerequisite not met: {prereq}")
                results["ready_for_execution"] = False

        # Risk assessment based on action type
        risk_level = self._assess_step_risk(workflow_step)
        results["estimated_risk"] = risk_level

        if risk_level == "high":
            results["warnings"].append("High-risk operation - extra caution required")

        return results

    async def _check_prerequisite(self, prerequisite: str, context: Dict[str, Any]) -> bool:
        """Check if a prerequisite is met"""
        # In production, this would check actual system state
        # For now, we'll simulate some basic checks

        prereq_lower = prerequisite.lower()

        if "backup" in prereq_lower:
            return context.get("backup_verified", True)
        elif "approval" in prereq_lower:
            return context.get("approval_received", False)
        elif "system" in prereq_lower:
            return context.get("system_available", True)
        else:
            return True  # Assume met for unknown prerequisites

    def _assess_step_risk(self, step: WorkflowStep) -> str:
        """Assess the risk level of a workflow step"""
        high_risk_actions = {
            "data_deletion", "data_modification", "data_transfer",
            "system_modification", "cross_border_transfer"
        }

        medium_risk_actions = {
            "data_access", "export", "notification",
            "consent_management", "access_control"
        }

        if step.action_type in high_risk_actions:
            return "high"
        elif step.action_type in medium_risk_actions:
            return "medium"
        else:
            return "low"