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
from .llm_service import LLMComplianceService

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
        self.llm_service = LLMComplianceService()
    
    async def initialize(self, secret_name: Optional[str] = None):
        """Initialize AI models and load training data"""
        logger.info("Initializing AI Compliance Analyzer")
        print("🤖 Initializing AI Compliance Analyzer...")
        
        # Initialize LLM service
        print(f"🔑 Initializing LLM service with secret: {secret_name}")
        llm_initialized = await self.llm_service.initialize(secret_name)
        if llm_initialized:
            logger.info("✅ LLM service initialized - AI suggestions enabled")
            print("✅ LLM service initialized - AI suggestions enabled")
        else:
            logger.warning("⚠️ LLM service not available - using fallback suggestions")
            print("⚠️ LLM service not available - using fallback suggestions")
        
        # Load risk patterns and compliance keywords
        await self._load_risk_patterns()
        await self._load_compliance_keywords()
        
        self.model_initialized = True
        logger.info("AI Compliance Analyzer initialized successfully")
        print(f"✅ AI Compliance Analyzer initialized with LLM: {llm_initialized}")
    
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
    
    async def analyze_text(self, text: str) -> str:
        """
        Analyze text content and provide AI-generated description
        
        Args:
            text: Text to analyze
            
        Returns:
            Generated description based on AI analysis
        """
        if not self.model_initialized:
            await self.initialize()
        
        # Use LLM service for advanced analysis
        try:
            # Extract violation context from the text for LLM analysis
            violation_data = self._extract_violation_context(text)
            
            # Get LLM-powered suggestion
            if self.llm_service.is_initialized:
                llm_result = await self.llm_service.generate_compliance_suggestion(
                    violation_data, 
                    violation_data.get('framework', 'PDPA')
                )
                
                logger.info("✅ Generated LLM-powered compliance suggestion")
                return llm_result.get('description', 'Compliance analysis completed with AI recommendations.')
            else:
                # Fallback to enhanced keyword analysis
                return self._enhanced_keyword_analysis(text)
            
        except Exception as e:
            logger.error(f"Error in LLM text analysis: {str(e)}")
            return self._enhanced_keyword_analysis(text)
    
    def _extract_violation_context(self, text: str) -> Dict[str, Any]:
        """Extract violation context from prompt text for LLM analysis"""
        context = {
            'customer_id': 'Unknown',
            'data_age_days': 0,
            'excess_days': 0,
            'retention_limit_days': 0,
            'is_archived': False,
            'framework': 'PDPA',
            'violation_type': 'DATA_RETENTION_EXCEEDED'
        }
        
        text_lower = text.lower()
        
        # Extract framework
        if 'pdpa' in text_lower or 'singapore' in text_lower:
            context['framework'] = 'PDPA'
        elif 'gdpr' in text_lower or 'eu' in text_lower:
            context['framework'] = 'GDPR'
        
        # Extract numeric values from text
        import re
        
        # Look for "data age: X days"
        age_match = re.search(r'data age[:\s]+(\d+)\s*days', text_lower)
        if age_match:
            context['data_age_days'] = int(age_match.group(1))
        
        # Look for "retention limit: X days"
        limit_match = re.search(r'retention limit[:\s]+(\d+)\s*days', text_lower)
        if limit_match:
            context['retention_limit_days'] = int(limit_match.group(1))
        
        # Look for "excess period: X days" or "exceeds X days"
        excess_match = re.search(r'excess[^:]*[:\s]+(\d+)\s*days', text_lower) or \
                     re.search(r'exceeds[^0-9]*(\d+)\s*days', text_lower)
        if excess_match:
            context['excess_days'] = int(excess_match.group(1))
        
        # Look for archived status
        if 'archived' in text_lower:
            context['is_archived'] = 'true' in text_lower or 'yes' in text_lower
        
        return context
    
    def _enhanced_keyword_analysis(self, text: str) -> str:
        """Enhanced keyword-based analysis as fallback"""
        text_lower = text.lower()
        
        # Check for compliance-related keywords
        if "retention" in text_lower and "days" in text_lower:
            if "exceeds" in text_lower or "over" in text_lower:
                return "Data retention period has been exceeded, requiring immediate review and potential deletion to ensure compliance with data protection regulations."
        
        if "pdpa" in text_lower or "singapore" in text_lower:
            return "Singapore PDPA compliance analysis indicates potential data protection issues requiring remediation."
        
        if "gdpr" in text_lower or "eu" in text_lower:
            return "EU GDPR compliance analysis shows potential privacy regulation violations that need attention."
        
        # Generic compliance analysis response
        return "Compliance analysis completed with recommendations for improving data protection practices."
    
    async def generate_violation_suggestions(
        self, 
        violation_data: Dict[str, Any], 
        framework: str = "PDPA"
    ) -> Dict[str, str]:
        """
        Generate comprehensive suggestions for a compliance violation
        
        Args:
            violation_data: Violation details
            framework: Compliance framework
            
        Returns:
            Dictionary with detailed suggestions and recommendations
        """
        if not self.model_initialized:
            await self.initialize()
        
        if self.llm_service.is_initialized:
            logger.info("🤖 Generating LLM-powered compliance suggestions")
            print(f"🤖 Requesting LLM analysis for {framework} violation...")
            return await self.llm_service.generate_compliance_suggestion(violation_data, framework)
        else:
            logger.warning("Using fallback compliance suggestions (LLM not available)")
            print("⚠️ Using fallback suggestions - LLM not available")
            return self.llm_service._get_fallback_suggestion(violation_data, framework)