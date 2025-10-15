"""
EDGP Master Data Compliance Orchestrator

Main orchestrator for running compliance scans and remediation
workflows for EDGP master data tables.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.compliance_agent.models.edgp_models import DataRetentionAnalysis, ComplianceViolationRecord
from src.compliance_agent.models.compliance_models import ComplianceFramework, RiskLevel
from src.compliance_agent.services.data_retention_scanner import DataRetentionScanner
from src.compliance_agent.services.remediation_integration_service import compliance_remediation_service
from src.compliance_agent.services.edgp_database_service_simple import EDGPDatabaseService

# Initialize service instance
edgp_db_service = EDGPDatabaseService()

logger = logging.getLogger(__name__)


class EDGPComplianceOrchestrator:
    """
    Main orchestrator for EDGP master data compliance operations
    
    This service coordinates between:
    1. Database scanning for compliance violations
    2. AI-powered analysis of violations
    3. Automatic remediation workflow creation
    4. Integration with remediation agent
    """
    
    def __init__(self):
        self.scanner = DataRetentionScanner()
        self.remediation_service = compliance_remediation_service
        
        # Configuration
        self.default_frameworks = [ComplianceFramework.GDPR_EU, ComplianceFramework.PDPA_SINGAPORE]
        self.scan_schedule_hours = 5/60  # Every 5 minutes
        self.auto_remediation_enabled = False
        self.critical_violation_threshold = 30  # days
        
        logger.info("EDGP Compliance Orchestrator initialized")
    
    async def run_comprehensive_compliance_scan(
        self,
        tables: Optional[List[str]] = None,
        compliance_framework: ComplianceFramework = ComplianceFramework.GDPR_EU,
        auto_remediate: bool = False,
        risk_threshold: Optional[RiskLevel] = RiskLevel.MEDIUM
    ) -> Dict[str, Any]:
        """
        Run a comprehensive compliance scan across all EDGP master data tables
        
        This is the main entry point for compliance scanning operations
        """
        
        logger.info("🔍 Starting comprehensive EDGP compliance scan")
        scan_start_time = datetime.utcnow()
        
        try:
            # Step 1: Scan for data retention violations
            logger.info("📊 Step 1: Scanning for data retention violations")
            analysis = await self.scanner.scan_all_tables(
                tables=tables or ["customer", "location", "vendor", "product"],
                compliance_framework=compliance_framework
            )
            
            # Step 2: Analyze violations and categorize by risk
            logger.info("⚠️ Step 2: Analyzing violations by risk level")
            risk_analysis = self._analyze_violations_by_risk(analysis.violations)
            
            # Step 3: Process high-priority violations immediately
            critical_violations = [v for v in analysis.violations if v.risk_level == RiskLevel.CRITICAL]
            high_violations = [v for v in analysis.violations if v.risk_level == RiskLevel.HIGH]
            
            remediation_summary = None
            if critical_violations or high_violations:
                logger.info(f"🚨 Step 3: Processing {len(critical_violations)} critical and {len(high_violations)} high violations")
                
                priority_violations = critical_violations + high_violations
                remediation_summary = await self.remediation_service.process_compliance_violations(
                    violations=priority_violations,
                    auto_execute=auto_remediate and self._should_auto_execute(priority_violations)
                )
            
            # Step 4: Handle medium and low priority violations based on threshold
            remaining_violations = [
                v for v in analysis.violations 
                if v.risk_level in [RiskLevel.MEDIUM, RiskLevel.LOW]
            ]
            
            if remaining_violations and risk_threshold and self._should_process_risk_level(risk_threshold):
                logger.info(f"⚡ Step 4: Processing {len(remaining_violations)} medium/low priority violations")
                
                filtered_violations = [
                    v for v in remaining_violations 
                    if self._meets_risk_threshold(v, risk_threshold)
                ]
                
                if filtered_violations:
                    additional_remediation = await self.remediation_service.process_compliance_violations(
                        violations=filtered_violations,
                        auto_execute=False  # Never auto-execute lower priority
                    )
                    
                    if remediation_summary:
                        # Merge remediation summaries
                        remediation_summary = self._merge_remediation_summaries(
                            remediation_summary, additional_remediation
                        )
                    else:
                        remediation_summary = additional_remediation
            
            # Step 5: Generate comprehensive report
            scan_duration = (datetime.utcnow() - scan_start_time).total_seconds()
            
            report = {
                "scan_summary": {
                    "scan_id": analysis.scan_id,
                    "scan_timestamp": analysis.scan_timestamp.isoformat(),
                    "scan_duration_seconds": scan_duration,
                    "compliance_framework": compliance_framework.value,
                    "tables_scanned": analysis.tables_scanned,
                    "total_records_scanned": analysis.total_records_scanned
                },
                "compliance_analysis": {
                    "overall_compliance_score": analysis.overall_compliance_score,
                    "compliance_status": analysis.compliance_status,
                    "total_violations": analysis.total_violations,
                    "violations_by_risk": analysis.violations_by_risk,
                    "violations_by_table": analysis.violations_by_table,
                    "violations_by_status": analysis.violations_by_status
                },
                "risk_analysis": risk_analysis,
                "remediation_summary": remediation_summary,
                "recommendations": self._generate_recommendations(analysis, risk_analysis),
                "next_scan_recommended": (datetime.utcnow() + timedelta(hours=self.scan_schedule_hours)).isoformat()
            }
            
            logger.info(f"✅ Compliance scan completed successfully in {scan_duration:.2f} seconds")
            logger.info(f"📋 Found {analysis.total_violations} violations with {analysis.overall_compliance_score}% compliance score")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Comprehensive compliance scan failed: {str(e)}")
            raise
    
    async def run_emergency_compliance_check(
        self,
        table_name: str,
        record_ids: Optional[List[int]] = None,
        immediate_remediation: bool = True
    ) -> Dict[str, Any]:
        """
        Run an emergency compliance check for specific records or table
        
        Used when immediate compliance verification is needed
        """
        
        logger.warning(f"🚨 Running emergency compliance check for {table_name}")
        
        try:
            # Initialize database
            await edgp_db_service.initialize()
            
            # Get specific records or all recent records
            if record_ids:
                # This would need specific record retrieval methods
                logger.info(f"Checking specific record IDs: {record_ids}")
            
            # For now, run full table scan
            analysis = await self.scanner.scan_all_tables(
                tables=[table_name],
                compliance_framework=ComplianceFramework.GDPR_EU
            )
            
            # Identify critical violations
            critical_violations = [
                v for v in analysis.violations 
                if v.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
            ]
            
            emergency_response = {
                "emergency_check_timestamp": datetime.utcnow().isoformat(),
                "table_name": table_name,
                "total_violations_found": len(analysis.violations),
                "critical_violations": len(critical_violations),
                "immediate_action_required": len(critical_violations) > 0,
                "violations": [
                    {
                        "record_id": v.record_id,
                        "record_code": v.record_code,
                        "risk_level": v.risk_level.value,
                        "days_overdue": v.days_overdue,
                        "retention_status": v.retention_status.value
                    }
                    for v in critical_violations
                ]
            }
            
            # Execute immediate remediation if requested
            if immediate_remediation and critical_violations:
                logger.warning(f"⚡ Executing immediate remediation for {len(critical_violations)} critical violations")
                
                remediation_result = await self.remediation_service.process_compliance_violations(
                    violations=critical_violations,
                    auto_execute=True
                )
                
                emergency_response["immediate_remediation"] = remediation_result
            
            return emergency_response
            
        except Exception as e:
            logger.error(f"Emergency compliance check failed: {str(e)}")
            raise
        finally:
            await edgp_db_service.close()
    
    async def schedule_regular_compliance_scans(
        self,
        interval_hours: float = 5/60,  # Every 5 minutes 
        enable_auto_remediation: bool = False
    ):
        """
        Schedule regular compliance scans
        
        This would typically be run as a background service
        """
        
        interval_minutes = interval_hours * 60
        logger.info(f"📅 Scheduling regular compliance scans every {interval_minutes:.1f} minutes")
        
        while True:
            try:
                logger.info("🔄 Running scheduled compliance scan")
                
                result = await self.run_comprehensive_compliance_scan(
                    auto_remediate=enable_auto_remediation,
                    risk_threshold=RiskLevel.HIGH
                )
                
                # Log summary
                violations = result["compliance_analysis"]["total_violations"]
                score = result["compliance_analysis"]["overall_compliance_score"]
                logger.info(f"📊 Scheduled scan complete: {violations} violations, {score}% compliance")
                
                # Sleep until next scan
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                logger.error(f"Scheduled compliance scan failed: {str(e)}")
                # Sleep for shorter time on error before retry
                await asyncio.sleep(3600)  # 1 hour retry
    
    def _analyze_violations_by_risk(
        self, 
        violations: List[ComplianceViolationRecord]
    ) -> Dict[str, Any]:
        """Analyze violations and provide risk insights"""
        
        if not violations:
            return {
                "total_violations": 0,
                "risk_distribution": {},
                "most_affected_table": None,
                "average_days_overdue": 0,
                "oldest_violation_days": 0,
                "recommendations": []
            }
        
        # Risk distribution
        risk_distribution = {}
        for risk_level in RiskLevel:
            count = len([v for v in violations if v.risk_level == risk_level])
            risk_distribution[risk_level.value] = {
                "count": count,
                "percentage": (count / len(violations)) * 100 if violations else 0
            }
        
        # Table analysis
        table_counts = {}
        for violation in violations:
            table_counts[violation.table_name] = table_counts.get(violation.table_name, 0) + 1
        
        most_affected_table = max(table_counts.items(), key=lambda x: x[1]) if table_counts else None
        
        # Time analysis
        days_overdue_list = [v.days_overdue for v in violations]
        average_days_overdue = sum(days_overdue_list) / len(days_overdue_list) if days_overdue_list else 0
        oldest_violation_days = max(days_overdue_list) if days_overdue_list else 0
        
        # Generate recommendations
        recommendations = []
        if risk_distribution.get("critical", {}).get("count", 0) > 0:
            recommendations.append("Immediate action required for critical violations")
        if average_days_overdue > 180:
            recommendations.append("Review data retention policies - violations are significantly overdue")
        if most_affected_table and most_affected_table[1] > len(violations) * 0.5:
            recommendations.append(f"Focus remediation efforts on {most_affected_table[0]} table")
        
        return {
            "total_violations": len(violations),
            "risk_distribution": risk_distribution,
            "most_affected_table": most_affected_table[0] if most_affected_table else None,
            "most_affected_table_count": most_affected_table[1] if most_affected_table else 0,
            "average_days_overdue": round(average_days_overdue, 1),
            "oldest_violation_days": oldest_violation_days,
            "recommendations": recommendations
        }
    
    def _should_auto_execute(self, violations: List[ComplianceViolationRecord]) -> bool:
        """Determine if violations should be auto-executed"""
        
        # Only auto-execute if all violations are clearly expired and low-risk data
        for violation in violations:
            # Don't auto-execute critical customer data
            if violation.table_name == "customer" and violation.risk_level == RiskLevel.CRITICAL:
                return False
            
            # Don't auto-execute if less than threshold days overdue
            if violation.days_overdue < self.critical_violation_threshold:
                return False
        
        return True
    
    def _should_process_risk_level(self, risk_threshold: RiskLevel) -> bool:
        """Check if we should process violations at this risk level"""
        return risk_threshold in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def _meets_risk_threshold(
        self, 
        violation: ComplianceViolationRecord, 
        threshold: RiskLevel
    ) -> bool:
        """Check if violation meets the risk threshold for processing"""
        
        risk_order = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        
        return risk_order.get(violation.risk_level, 0) >= risk_order.get(threshold, 0)
    
    def _merge_remediation_summaries(
        self, 
        summary1: Dict[str, Any], 
        summary2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two remediation summaries"""
        
        return {
            "total_violations": summary1.get("total_violations", 0) + summary2.get("total_violations", 0),
            "successful_remediations": summary1.get("successful_remediations", 0) + summary2.get("successful_remediations", 0),
            "failed_remediations": summary1.get("failed_remediations", 0) + summary2.get("failed_remediations", 0),
            "skipped_violations": summary1.get("skipped_violations", 0) + summary2.get("skipped_violations", 0),
            "remediation_details": summary1.get("remediation_details", []) + summary2.get("remediation_details", []),
            "errors": summary1.get("errors", []) + summary2.get("errors", [])
        }
    
    def _generate_recommendations(
        self, 
        analysis: DataRetentionAnalysis, 
        risk_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        
        recommendations = []
        
        # Compliance score recommendations
        if analysis.overall_compliance_score < 60:
            recommendations.append("🚨 URGENT: Compliance score is critically low. Immediate remediation required.")
        elif analysis.overall_compliance_score < 80:
            recommendations.append("⚠️ WARNING: Compliance score below acceptable threshold. Plan remediation activities.")
        
        # Risk-based recommendations
        critical_count = analysis.violations_by_risk.get(RiskLevel.CRITICAL, 0)
        if critical_count > 0:
            recommendations.append(f"🔴 Address {critical_count} critical violations immediately")
        
        high_count = analysis.violations_by_risk.get(RiskLevel.HIGH, 0)
        if high_count > 0:
            recommendations.append(f"🟡 Schedule remediation for {high_count} high-risk violations within 7 days")
        
        # Table-specific recommendations
        for table_name, violation_count in analysis.violations_by_table.items():
            if violation_count > 10:
                recommendations.append(f"📊 Review data retention policy for {table_name} table ({violation_count} violations)")
        
        # Process recommendations
        if analysis.records_requiring_deletion > 0:
            recommendations.append(f"🗑️ {analysis.records_requiring_deletion} records ready for deletion")
        
        if analysis.records_requiring_review > 0:
            recommendations.append(f"👀 {analysis.records_requiring_review} records require manual review")
        
        # General recommendations
        recommendations.extend([
            "📋 Review and update data retention policies regularly",
            "🔄 Schedule automated compliance scans",
            "📊 Monitor compliance dashboard for trends",
            "🛡️ Implement data governance controls"
        ])
        
        return recommendations


# Global orchestrator instance
edgp_compliance_orchestrator = EDGPComplianceOrchestrator()