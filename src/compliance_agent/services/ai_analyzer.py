"""
AI-powered Compliance Analyzer
Uses machine learning and NLP to analyze compliance beyond rule-based checks.
"""

import asyncio
from typing import Dict, Any, List, Optional
import json

from ..models.compliance_models import (
    ComplianceFramework,
    DataProcessingActivity,
    DataType,
    RiskLevel,
    ComplianceViolation
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AIComplianceAnalyzer:
    """
    AI-powered compliance analyzer that uses natural language processing
    and machine learning to identify compliance issues.
    """
    
    def __init__(self):
        self.model_initialized = False
        self.risk_patterns = {}
        self.compliance_keywords = {}
    
    async def initialize(self):
        """Initialize AI models and load training data"""
        logger.info("Initializing AI Compliance Analyzer")
        
        # Load risk patterns and compliance keywords
        await self._load_risk_patterns()
        await self._load_compliance_keywords()
        
        self.model_initialized = True
        logger.info("AI Compliance Analyzer initialized successfully")
    
    async def analyze_activity(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """
        Perform AI-powered analysis of a data processing activity
        
        Args:
            activity: Data processing activity to analyze
            framework: Compliance framework to analyze against
            
        Returns:
            Dictionary containing analysis results with violations and recommendations
        """
        if not self.model_initialized:
            await self.initialize()
        
        logger.info(f"AI analyzing activity {activity.id} for {framework}")
        
        analysis_result = {
            "violations": [],
            "recommendations": [],
            "confidence_scores": {},
            "risk_indicators": []
        }
        
        # Analyze text for compliance issues
        text_analysis = await self._analyze_text_compliance(activity, framework)
        analysis_result["violations"].extend(text_analysis.get("violations", []))
        analysis_result["recommendations"].extend(text_analysis.get("recommendations", []))
        
        # Analyze data flow patterns
        data_flow_analysis = await self._analyze_data_flow_patterns(activity, framework)
        analysis_result["violations"].extend(data_flow_analysis.get("violations", []))
        analysis_result["recommendations"].extend(data_flow_analysis.get("recommendations", []))
        
        # Analyze cross-border transfer risks
        transfer_analysis = await self._analyze_transfer_risks(activity, framework)
        analysis_result["violations"].extend(transfer_analysis.get("violations", []))
        analysis_result["recommendations"].extend(transfer_analysis.get("recommendations", []))
        
        # Analyze automated decision making
        automation_analysis = await self._analyze_automation_risks(activity, framework)
        analysis_result["violations"].extend(automation_analysis.get("violations", []))
        analysis_result["recommendations"].extend(automation_analysis.get("recommendations", []))
        
        logger.info(f"AI analysis completed: {len(analysis_result['violations'])} violations, {len(analysis_result['recommendations'])} recommendations")
        return analysis_result
    
    async def _load_risk_patterns(self):
        """Load AI risk detection patterns"""
        # In a real implementation, this would load from trained models
        self.risk_patterns = {
            ComplianceFramework.PDPA_SINGAPORE: {
                "high_risk_keywords": ["biometric", "genetic", "health", "financial", "criminal"],
                "consent_indicators": ["consent", "agree", "permission", "authorization"],
                "purpose_indicators": ["purpose", "reason", "objective", "goal"]
            },
            ComplianceFramework.GDPR_EU: {
                "high_risk_keywords": ["profiling", "automated", "large_scale", "vulnerable"],
                "lawful_basis_indicators": ["consent", "contract", "legal_obligation", "vital_interests", "public_task", "legitimate_interests"],
                "special_category_indicators": ["racial", "ethnic", "political", "religious", "health", "sexual", "biometric", "genetic"]
            }
        }
    
    async def _load_compliance_keywords(self):
        """Load compliance-related keywords and phrases"""
        self.compliance_keywords = {
            "positive_indicators": [
                "data protection", "privacy by design", "consent management",
                "data minimization", "purpose limitation", "storage limitation",
                "accuracy", "security", "accountability", "transparency"
            ],
            "negative_indicators": [
                "unlimited retention", "blanket consent", "unnecessary collection",
                "unclear purpose", "insecure transmission", "no access controls"
            ]
        }
    
    async def _analyze_text_compliance(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """Analyze text content for compliance issues using NLP"""
        
        violations = []
        recommendations = []
        
        # Combine all text fields for analysis
        text_content = f"{activity.name} {activity.purpose} {' '.join(activity.legal_bases)} {' '.join(activity.recipients)}"
        text_lower = text_content.lower()
        
        # Check for framework-specific risk patterns
        if framework in self.risk_patterns:
            patterns = self.risk_patterns[framework]
            
            # Check for high-risk keywords
            high_risk_found = any(keyword in text_lower for keyword in patterns.get("high_risk_keywords", []))
            if high_risk_found:
                violations.append(
                    ComplianceViolation(
                        rule_id=f"ai_analysis_{framework}_high_risk",
                        activity_id=activity.id,
                        description="AI detected high-risk data processing indicators",
                        risk_level=RiskLevel.HIGH,
                        remediation_actions=[
                            "Conduct detailed risk assessment for high-risk data processing",
                            "Implement additional safeguards and controls",
                            "Consider Data Protection Impact Assessment"
                        ]
                    )
                )
        
        # Check for vague or unclear purposes
        if len(activity.purpose.strip()) < 20:
            recommendations.append("Provide more detailed and specific purpose description")
        
        # Check for generic consent language
        if "consent" in text_lower and any(word in text_lower for word in ["general", "broad", "any", "all"]):
            violations.append(
                ComplianceViolation(
                    rule_id=f"ai_analysis_{framework}_vague_consent",
                    activity_id=activity.id,
                    description="AI detected potentially vague or overly broad consent language",
                    risk_level=RiskLevel.MEDIUM,
                    remediation_actions=[
                        "Make consent requests more specific and granular",
                        "Clearly specify what data is collected and why",
                        "Allow separate consent for different purposes"
                    ]
                )
            )
        
        return {"violations": violations, "recommendations": recommendations}
    
    async def _analyze_data_flow_patterns(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """Analyze data flow patterns for compliance risks"""
        
        violations = []
        recommendations = []
        
        # Check for unusual data type combinations
        sensitive_types = [DataType.SENSITIVE_DATA, DataType.HEALTH_DATA, DataType.BIOMETRIC_DATA, DataType.FINANCIAL_DATA]
        has_sensitive = any(dt in sensitive_types for dt in activity.data_types)
        
        if has_sensitive and len(activity.recipients) > 3:
            violations.append(
                ComplianceViolation(
                    rule_id=f"ai_analysis_{framework}_excessive_sharing",
                    activity_id=activity.id,
                    description="AI detected potential excessive sharing of sensitive data",
                    risk_level=RiskLevel.HIGH,
                    remediation_actions=[
                        "Review necessity of sharing sensitive data with multiple recipients",
                        "Implement data sharing agreements with all recipients",
                        "Consider data minimization techniques"
                    ]
                )
            )
        
        # Check for missing retention period on sensitive data
        if has_sensitive and not activity.retention_period:
            recommendations.append("Define specific retention periods for sensitive data types")
        
        return {"violations": violations, "recommendations": recommendations}
    
    async def _analyze_transfer_risks(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """Analyze cross-border transfer risks"""
        
        violations = []
        recommendations = []
        
        if activity.cross_border_transfers:
            # For GDPR, check for adequacy decisions or appropriate safeguards
            if framework == ComplianceFramework.GDPR_EU:
                if not any("adequacy" in basis.lower() or "safeguards" in basis.lower() for basis in activity.legal_bases):
                    violations.append(
                        ComplianceViolation(
                            rule_id=f"ai_analysis_{framework}_transfer_safeguards",
                            activity_id=activity.id,
                            description="AI detected potential cross-border transfer without adequate safeguards",
                            risk_level=RiskLevel.HIGH,
                            remediation_actions=[
                                "Verify adequacy decision for destination country",
                                "Implement appropriate safeguards (SCCs, BCRs, etc.)",
                                "Document transfer impact assessment"
                            ]
                        )
                    )
            
            # For PDPA Singapore, check notification requirements
            elif framework == ComplianceFramework.PDPA_SINGAPORE:
                recommendations.append("Ensure compliance with PDPA transfer notification requirements")
        
        return {"violations": violations, "recommendations": recommendations}
    
    async def _analyze_automation_risks(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> Dict[str, Any]:
        """Analyze automated decision-making risks"""
        
        violations = []
        recommendations = []
        
        if activity.automated_decision_making:
            # Check for human oversight mechanisms
            if framework == ComplianceFramework.GDPR_EU:
                recommendations.extend([
                    "Implement human oversight for automated decision-making",
                    "Provide information about automated decision-making logic",
                    "Allow data subjects to contest automated decisions"
                ])
            
            # Check for high-risk automated processing
            sensitive_types = [DataType.SENSITIVE_DATA, DataType.HEALTH_DATA, DataType.FINANCIAL_DATA]
            if any(dt in sensitive_types for dt in activity.data_types):
                violations.append(
                    ComplianceViolation(
                        rule_id=f"ai_analysis_{framework}_high_risk_automation",
                        activity_id=activity.id,
                        description="AI detected high-risk automated processing of sensitive data",
                        risk_level=RiskLevel.HIGH,
                        remediation_actions=[
                            "Conduct DPIA for high-risk automated processing",
                            "Implement enhanced transparency measures",
                            "Provide meaningful human review capabilities"
                        ]
                    )
                )
        
        return {"violations": violations, "recommendations": recommendations}
    
    async def predict_compliance_score(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework
    ) -> float:
        """
        Use AI to predict compliance score
        
        Args:
            activity: Data processing activity
            framework: Compliance framework
            
        Returns:
            Predicted compliance score (0-100)
        """
        # In a real implementation, this would use trained ML models
        # For now, we'll use a heuristic approach
        
        base_score = 100.0
        
        # Deduct points for risk factors
        risk_factors = {
            "no_purpose": 15,
            "no_legal_basis": 20,
            "sensitive_data": 10,
            "cross_border": 10,
            "automated_decisions": 15,
            "many_recipients": 10,
            "no_retention_period": 5
        }
        
        if not activity.purpose or len(activity.purpose.strip()) < 10:
            base_score -= risk_factors["no_purpose"]
        
        if not activity.legal_bases:
            base_score -= risk_factors["no_legal_basis"]
        
        sensitive_types = [DataType.SENSITIVE_DATA, DataType.HEALTH_DATA, DataType.BIOMETRIC_DATA]
        if any(dt in sensitive_types for dt in activity.data_types):
            base_score -= risk_factors["sensitive_data"]
        
        if activity.cross_border_transfers:
            base_score -= risk_factors["cross_border"]
        
        if activity.automated_decision_making:
            base_score -= risk_factors["automated_decisions"]
        
        if len(activity.recipients) > 5:
            base_score -= risk_factors["many_recipients"]
        
        if not activity.retention_period:
            base_score -= risk_factors["no_retention_period"]
        
        return max(0.0, base_score)