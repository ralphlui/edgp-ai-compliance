"""
Compliance Rule Engine
Handles rule-based compliance checking against various frameworks.
"""

import json
import asyncio
from typing import List, Dict, Optional
from pathlib import Path

from ..models.compliance_models import (
    ComplianceFramework,
    ComplianceRule,
    ComplianceViolation,
    DataProcessingActivity,
    DataType,
    RiskLevel
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ComplianceRuleEngine:
    """
    Rule-based compliance checking engine that evaluates data processing
    activities against predefined compliance rules.
    """
    
    def __init__(self):
        self.rules: Dict[ComplianceFramework, List[ComplianceRule]] = {}
        self._rules_loaded = False
    
    async def load_rules(self):
        """Load compliance rules from configuration"""
        logger.info("Loading compliance rules")
        
        # Load PDPA Singapore rules
        pdpa_rules = self._create_pdpa_rules()
        self.rules[ComplianceFramework.PDPA_SINGAPORE] = pdpa_rules
        
        # Load GDPR rules
        gdpr_rules = self._create_gdpr_rules()
        self.rules[ComplianceFramework.GDPR_EU] = gdpr_rules
        
        # Load other framework rules
        self.rules[ComplianceFramework.CCPA_CALIFORNIA] = self._create_ccpa_rules()
        self.rules[ComplianceFramework.ISO_27001] = self._create_iso27001_rules()
        
        self._rules_loaded = True
        logger.info(f"Loaded rules for {len(self.rules)} frameworks")
    
    async def get_rules_for_framework(self, framework: ComplianceFramework) -> List[ComplianceRule]:
        """Get all rules for a specific framework"""
        if not self._rules_loaded:
            await self.load_rules()
        
        return self.rules.get(framework, [])
    
    async def check_rule_compliance(
        self,
        activity: DataProcessingActivity,
        rule: ComplianceRule
    ) -> Optional[ComplianceViolation]:
        """
        Check if a data processing activity violates a specific rule
        
        Args:
            activity: Data processing activity to check
            rule: Compliance rule to check against
            
        Returns:
            ComplianceViolation if rule is violated, None otherwise
        """
        # Check if rule applies to this activity's data types
        if not any(dt in rule.applicable_data_types for dt in activity.data_types):
            return None
        
        # Rule-specific compliance checks
        violation = None
        
        if rule.framework == ComplianceFramework.PDPA_SINGAPORE:
            violation = await self._check_pdpa_rule(activity, rule)
        elif rule.framework == ComplianceFramework.GDPR_EU:
            violation = await self._check_gdpr_rule(activity, rule)
        elif rule.framework == ComplianceFramework.CCPA_CALIFORNIA:
            violation = await self._check_ccpa_rule(activity, rule)
        elif rule.framework == ComplianceFramework.ISO_27001:
            violation = await self._check_iso27001_rule(activity, rule)
        
        return violation
    
    def _create_pdpa_rules(self) -> List[ComplianceRule]:
        """Create PDPA Singapore compliance rules"""
        return [
            ComplianceRule(
                id="pdpa_consent_001",
                framework=ComplianceFramework.PDPA_SINGAPORE,
                article="Section 13",
                title="Consent for Collection, Use or Disclosure",
                description="Personal data must not be collected, used or disclosed without consent",
                requirements=[
                    "Obtain consent before collecting personal data",
                    "Consent must be informed and voluntary",
                    "Consent can be withdrawn at any time"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA],
                severity=RiskLevel.HIGH
            ),
            ComplianceRule(
                id="pdpa_purpose_001",
                framework=ComplianceFramework.PDPA_SINGAPORE,
                article="Section 15",
                title="Purpose Limitation",
                description="Personal data must be collected for a reasonable purpose",
                requirements=[
                    "Collection must be for a reasonable purpose",
                    "Purpose must be made known at time of collection",
                    "Data must not be used for purposes incompatible with original purpose"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA],
                severity=RiskLevel.MEDIUM
            ),
            ComplianceRule(
                id="pdpa_notification_001",
                framework=ComplianceFramework.PDPA_SINGAPORE,
                article="Section 20",
                title="Notification of Data Breach",
                description="Organizations must notify PDPC of data breaches",
                requirements=[
                    "Notify PDPC within 72 hours if breach affects 500+ individuals",
                    "Notify affected individuals if breach likely to cause significant harm",
                    "Assessment must be documented"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA, DataType.FINANCIAL_DATA],
                severity=RiskLevel.CRITICAL
            ),
            ComplianceRule(
                id="pdpa_protection_001",
                framework=ComplianceFramework.PDPA_SINGAPORE,
                article="Section 24",
                title="Protection Obligation",
                description="Organizations must protect personal data in their possession",
                requirements=[
                    "Implement reasonable security arrangements",
                    "Protect against unauthorized access, collection, use, disclosure, copying, modification, disposal or similar risks",
                    "Security measures must be proportionate to nature of data"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA, DataType.FINANCIAL_DATA, DataType.HEALTH_DATA],
                severity=RiskLevel.HIGH
            )
        ]
    
    def _create_gdpr_rules(self) -> List[ComplianceRule]:
        """Create GDPR compliance rules"""
        return [
            ComplianceRule(
                id="gdpr_lawful_basis_001",
                framework=ComplianceFramework.GDPR_EU,
                article="Article 6",
                title="Lawful Basis for Processing",
                description="Processing must have a lawful basis",
                requirements=[
                    "Must have one of six lawful bases for processing",
                    "Lawful basis must be determined before processing begins",
                    "Cannot switch lawful basis during processing"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA],
                severity=RiskLevel.HIGH
            ),
            ComplianceRule(
                id="gdpr_special_categories_001",
                framework=ComplianceFramework.GDPR_EU,
                article="Article 9",
                title="Special Categories of Personal Data",
                description="Processing of special categories requires explicit consent or other conditions",
                requirements=[
                    "Explicit consent required for special categories",
                    "Additional safeguards must be implemented",
                    "DPO consultation may be required"
                ],
                applicable_data_types=[DataType.SENSITIVE_DATA, DataType.HEALTH_DATA, DataType.BIOMETRIC_DATA],
                severity=RiskLevel.CRITICAL
            ),
            ComplianceRule(
                id="gdpr_data_subject_rights_001",
                framework=ComplianceFramework.GDPR_EU,
                article="Articles 15-22",
                title="Data Subject Rights",
                description="Data subjects have various rights regarding their personal data",
                requirements=[
                    "Provide mechanisms for exercising rights",
                    "Respond to requests within one month",
                    "Verify identity of requestor"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA],
                severity=RiskLevel.MEDIUM
            ),
            ComplianceRule(
                id="gdpr_dpia_001",
                framework=ComplianceFramework.GDPR_EU,
                article="Article 35",
                title="Data Protection Impact Assessment",
                description="DPIA required for high-risk processing",
                requirements=[
                    "Conduct DPIA for high-risk processing",
                    "Consult with DPO if applicable",
                    "Consult with supervisory authority if residual high risk"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.SENSITIVE_DATA, DataType.BIOMETRIC_DATA],
                severity=RiskLevel.HIGH
            )
        ]
    
    def _create_ccpa_rules(self) -> List[ComplianceRule]:
        """Create CCPA compliance rules"""
        return [
            ComplianceRule(
                id="ccpa_notice_001",
                framework=ComplianceFramework.CCPA_CALIFORNIA,
                article="Section 1798.100",
                title="Consumer Right to Know",
                description="Consumers have the right to know about personal information collection",
                requirements=[
                    "Provide notice at or before collection",
                    "Describe categories of personal information",
                    "Describe purposes for collection"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.BEHAVIORAL_DATA],
                severity=RiskLevel.MEDIUM
            )
        ]
    
    def _create_iso27001_rules(self) -> List[ComplianceRule]:
        """Create ISO 27001 compliance rules"""
        return [
            ComplianceRule(
                id="iso27001_access_control_001",
                framework=ComplianceFramework.ISO_27001,
                article="A.9.1.1",
                title="Access Control Policy",
                description="Access control policy must be established and documented",
                requirements=[
                    "Establish access control policy",
                    "Document access control procedures",
                    "Regular review of access rights"
                ],
                applicable_data_types=[DataType.PERSONAL_DATA, DataType.FINANCIAL_DATA, DataType.SENSITIVE_DATA],
                severity=RiskLevel.MEDIUM
            )
        ]
    
    async def _check_pdpa_rule(
        self,
        activity: DataProcessingActivity,
        rule: ComplianceRule
    ) -> Optional[ComplianceViolation]:
        """Check PDPA-specific rule compliance"""
        
        if rule.id == "pdpa_consent_001":
            # Check if consent is obtained for personal data collection
            if not activity.legal_bases or "consent" not in [lb.lower() for lb in activity.legal_bases]:
                return ComplianceViolation(
                    rule_id=rule.id,
                    activity_id=activity.id,
                    description="Personal data collection without proper consent",
                    risk_level=rule.severity,
                    remediation_actions=[
                        "Implement consent collection mechanism",
                        "Update privacy policy to clearly state consent requirements",
                        "Provide mechanism for consent withdrawal"
                    ]
                )
        
        elif rule.id == "pdpa_purpose_001":
            # Check if purpose is clearly defined
            if not activity.purpose or len(activity.purpose.strip()) < 10:
                return ComplianceViolation(
                    rule_id=rule.id,
                    activity_id=activity.id,
                    description="Purpose of data collection not clearly defined",
                    risk_level=rule.severity,
                    remediation_actions=[
                        "Clearly define and document purpose of data collection",
                        "Ensure purpose is communicated to data subjects",
                        "Limit processing to stated purposes"
                    ]
                )
        
        elif rule.id == "pdpa_protection_001":
            # Check if security measures are mentioned
            if not any("security" in lb.lower() or "protection" in lb.lower() for lb in activity.legal_bases):
                return ComplianceViolation(
                    rule_id=rule.id,
                    activity_id=activity.id,
                    description="No security measures documented for personal data protection",
                    risk_level=rule.severity,
                    remediation_actions=[
                        "Implement appropriate technical and organizational measures",
                        "Document security measures in place",
                        "Regular security assessments and updates"
                    ]
                )
        
        return None
    
    async def _check_gdpr_rule(
        self,
        activity: DataProcessingActivity,
        rule: ComplianceRule
    ) -> Optional[ComplianceViolation]:
        """Check GDPR-specific rule compliance"""
        
        if rule.id == "gdpr_lawful_basis_001":
            # Check if lawful basis is specified
            valid_bases = ["consent", "contract", "legal_obligation", "vital_interests", "public_task", "legitimate_interests"]
            if not any(basis.lower() in [vb for vb in valid_bases] for basis in activity.legal_bases):
                return ComplianceViolation(
                    rule_id=rule.id,
                    activity_id=activity.id,
                    description="No valid lawful basis specified for processing",
                    risk_level=rule.severity,
                    remediation_actions=[
                        "Identify and document appropriate lawful basis",
                        "Update privacy policy with lawful basis information",
                        "Ensure lawful basis is communicated to data subjects"
                    ]
                )
        
        elif rule.id == "gdpr_special_categories_001":
            # Check if special categories require explicit consent
            special_data_types = [DataType.SENSITIVE_DATA, DataType.HEALTH_DATA, DataType.BIOMETRIC_DATA]
            if any(dt in special_data_types for dt in activity.data_types):
                if "explicit_consent" not in [lb.lower() for lb in activity.legal_bases]:
                    return ComplianceViolation(
                        rule_id=rule.id,
                        activity_id=activity.id,
                        description="Special category data processing without explicit consent",
                        risk_level=rule.severity,
                        remediation_actions=[
                            "Obtain explicit consent for special category data",
                            "Implement additional safeguards",
                            "Consider alternative lawful bases if available"
                        ]
                    )
        
        return None
    
    async def _check_ccpa_rule(
        self,
        activity: DataProcessingActivity,
        rule: ComplianceRule
    ) -> Optional[ComplianceViolation]:
        """Check CCPA-specific rule compliance"""
        # Basic CCPA compliance check
        return None
    
    async def _check_iso27001_rule(
        self,
        activity: DataProcessingActivity,
        rule: ComplianceRule
    ) -> Optional[ComplianceViolation]:
        """Check ISO 27001-specific rule compliance"""
        # Basic ISO 27001 compliance check
        return None