"""
Core AI Compliance Engine
This module contains the main AI-powered compliance analysis engine.
"""

import asyncio
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..models.compliance_models import (
    ComplianceFramework,
    DataProcessingActivity,
    ComplianceAssessment,
    ComplianceViolation,
    ComplianceRule,
    ComplianceStatus,
    RiskLevel,
    PrivacyImpactAssessment
)
from ..services.rule_engine import ComplianceRuleEngine
from ..services.ai_analyzer import AIComplianceAnalyzer
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ComplianceEngine:
    """
    Core AI-powered compliance engine that orchestrates compliance checking
    across multiple frameworks and regulations.
    """
    
    def __init__(self):
        self.rule_engine = ComplianceRuleEngine()
        self.ai_analyzer = AIComplianceAnalyzer()
        self._rules_cache: Dict[ComplianceFramework, List[ComplianceRule]] = {}
        
    async def initialize(self):
        """Initialize the compliance engine with rules and AI models"""
        logger.info("Initializing Compliance Engine")
        await self.rule_engine.load_rules()
        await self.ai_analyzer.initialize()
        logger.info("Compliance Engine initialized successfully")
    
    async def assess_compliance(
        self,
        activity: DataProcessingActivity,
        frameworks: List[ComplianceFramework],
        include_ai_analysis: bool = True
    ) -> List[ComplianceAssessment]:
        """
        Assess compliance of a data processing activity against specified frameworks
        
        Args:
            activity: The data processing activity to assess
            frameworks: List of compliance frameworks to check against
            include_ai_analysis: Whether to include AI-powered analysis
            
        Returns:
            List of compliance assessments, one per framework
        """
        logger.info(f"Assessing compliance for activity {activity.id} against {len(frameworks)} frameworks")
        
        assessments = []
        
        for framework in frameworks:
            try:
                assessment = await self._assess_single_framework(
                    activity, framework, include_ai_analysis
                )
                assessments.append(assessment)
            except Exception as e:
                logger.error(f"Error assessing {framework}: {str(e)}")
                # Create a failed assessment
                assessment = ComplianceAssessment(
                    id=f"{activity.id}_{framework}_{datetime.utcnow().isoformat()}",
                    framework=framework,
                    activity=activity,
                    status=ComplianceStatus.UNKNOWN,
                    score=0.0,
                    assessor="ai_compliance_engine",
                    violations=[],
                    recommendations=[f"Assessment failed: {str(e)}"]
                )
                assessments.append(assessment)
        
        return assessments
    
    async def _assess_single_framework(
        self,
        activity: DataProcessingActivity,
        framework: ComplianceFramework,
        include_ai_analysis: bool
    ) -> ComplianceAssessment:
        """Assess compliance against a single framework"""
        
        # Get relevant rules for this framework
        rules = await self.rule_engine.get_rules_for_framework(framework)
        
        # Check rule-based compliance
        violations = await self._check_rule_violations(activity, rules)
        
        # AI-powered analysis if requested
        ai_violations = []
        ai_recommendations = []
        
        if include_ai_analysis:
            ai_analysis = await self.ai_analyzer.analyze_activity(activity, framework)
            ai_violations.extend(ai_analysis.get('violations', []))
            ai_recommendations.extend(ai_analysis.get('recommendations', []))
        
        # Combine all violations
        all_violations = violations + ai_violations
        
        # Calculate compliance score
        score = self._calculate_compliance_score(all_violations, rules)
        
        # Determine overall status
        status = self._determine_compliance_status(all_violations)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_violations, rules)
        recommendations.extend(ai_recommendations)
        
        assessment = ComplianceAssessment(
            id=f"{activity.id}_{framework}_{datetime.utcnow().isoformat()}",
            framework=framework,
            activity=activity,
            status=status,
            score=score,
            violations=all_violations,
            recommendations=recommendations,
            assessor="ai_compliance_engine"
        )
        
        logger.info(f"Assessment completed for {framework}: Status={status}, Score={score}")
        return assessment
    
    async def _check_rule_violations(
        self,
        activity: DataProcessingActivity,
        rules: List[ComplianceRule]
    ) -> List[ComplianceViolation]:
        """Check for rule-based compliance violations"""
        violations = []
        
        for rule in rules:
            violation = await self.rule_engine.check_rule_compliance(activity, rule)
            if violation:
                violations.append(violation)
        
        return violations
    
    def _calculate_compliance_score(
        self,
        violations: List[ComplianceViolation],
        rules: List[ComplianceRule]
    ) -> float:
        """Calculate a compliance score based on violations"""
        if not rules:
            return 100.0
        
        if not violations:
            return 100.0
        
        # Weight violations by severity
        severity_weights = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 3,
            RiskLevel.HIGH: 7,
            RiskLevel.CRITICAL: 15
        }
        
        total_weight = sum(severity_weights[v.risk_level] for v in violations)
        max_possible_weight = len(rules) * severity_weights[RiskLevel.CRITICAL]
        
        if max_possible_weight == 0:
            return 100.0
        
        penalty = (total_weight / max_possible_weight) * 100
        score = max(0.0, 100.0 - penalty)
        
        return round(score, 2)
    
    def _determine_compliance_status(self, violations: List[ComplianceViolation]) -> ComplianceStatus:
        """Determine overall compliance status based on violations"""
        if not violations:
            return ComplianceStatus.COMPLIANT
        
        critical_violations = [v for v in violations if v.risk_level == RiskLevel.CRITICAL]
        high_violations = [v for v in violations if v.risk_level == RiskLevel.HIGH]
        
        if critical_violations:
            return ComplianceStatus.NON_COMPLIANT
        elif high_violations:
            return ComplianceStatus.REQUIRES_REVIEW
        else:
            return ComplianceStatus.REQUIRES_REVIEW
    
    def _generate_recommendations(
        self,
        violations: List[ComplianceViolation],
        rules: List[ComplianceRule]
    ) -> List[str]:
        """Generate compliance improvement recommendations"""
        recommendations = []
        
        for violation in violations:
            recommendations.extend(violation.remediation_actions)
        
        # Add general recommendations based on missing compliance areas
        if violations:
            recommendations.append("Conduct a comprehensive data protection impact assessment")
            recommendations.append("Review and update privacy policies and consent mechanisms")
            recommendations.append("Implement additional technical and organizational measures")
        
        return list(set(recommendations))  # Remove duplicates
    
    async def conduct_privacy_impact_assessment(
        self,
        project_name: str,
        description: str,
        processing_activities: List[DataProcessingActivity]
    ) -> PrivacyImpactAssessment:
        """
        Conduct a Privacy Impact Assessment (PIA/DPIA)
        """
        logger.info(f"Conducting Privacy Impact Assessment for project: {project_name}")
        
        # Analyze all processing activities
        risk_scores = {}
        all_data_types = set()
        
        for activity in processing_activities:
            # Assess each activity across relevant frameworks
            frameworks = [ComplianceFramework.PDPA_SINGAPORE, ComplianceFramework.GDPR_EU]
            assessments = await self.assess_compliance(activity, frameworks)
            
            # Calculate risk score for this activity
            avg_score = sum(a.score for a in assessments) / len(assessments)
            risk_scores[activity.id] = 100 - avg_score  # Higher score = lower risk
            
            all_data_types.update(activity.data_types)
        
        # Determine overall risk level
        max_risk_score = max(risk_scores.values()) if risk_scores else 0
        overall_risk = self._risk_score_to_level(max_risk_score)
        
        # Generate mitigation measures based on identified risks
        mitigation_measures = self._generate_mitigation_measures(processing_activities, overall_risk)
        
        # Determine if DPA consultation is required
        requires_consultation = (
            overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL] or
            any(activity.automated_decision_making for activity in processing_activities) or
            any(activity.cross_border_transfers for activity in processing_activities)
        )
        
        pia = PrivacyImpactAssessment(
            id=f"pia_{project_name.lower().replace(' ', '_')}_{datetime.utcnow().isoformat()}",
            project_name=project_name,
            description=description,
            data_types=list(all_data_types),
            processing_activities=processing_activities,
            risk_assessment=risk_scores,
            mitigation_measures=mitigation_measures,
            overall_risk=overall_risk,
            requires_consultation=requires_consultation
        )
        
        logger.info(f"PIA completed for {project_name}: Overall risk={overall_risk}")
        return pia
    
    def _risk_score_to_level(self, score: float) -> RiskLevel:
        """Convert a risk score to a risk level"""
        if score >= 75:
            return RiskLevel.CRITICAL
        elif score >= 50:
            return RiskLevel.HIGH
        elif score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_mitigation_measures(
        self,
        activities: List[DataProcessingActivity],
        risk_level: RiskLevel
    ) -> List[str]:
        """Generate risk mitigation measures based on processing activities and risk level"""
        measures = []
        
        # Base measures for all risk levels
        measures.extend([
            "Implement data minimization principles",
            "Ensure transparent data processing through clear privacy notices",
            "Establish procedures for handling data subject rights requests",
            "Implement appropriate technical and organizational measures"
        ])
        
        # Additional measures based on risk level
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            measures.extend([
                "Conduct regular privacy audits and assessments",
                "Implement privacy by design and by default",
                "Establish data breach response procedures",
                "Consider appointment of Data Protection Officer",
                "Implement enhanced access controls and monitoring"
            ])
        
        # Activity-specific measures
        if any(activity.cross_border_transfers for activity in activities):
            measures.append("Implement appropriate safeguards for international data transfers")
        
        if any(activity.automated_decision_making for activity in activities):
            measures.append("Implement measures to address automated decision-making risks")
        
        return measures