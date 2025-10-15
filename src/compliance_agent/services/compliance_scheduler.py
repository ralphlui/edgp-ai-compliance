#!/usr/bin/env python3
"""
Async Periodic Scheduler for International AI Compliance Agent
Runs automatic compliance checks without user interaction
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
import structlog

from src.compliance_agent.international_ai_agent import InternationalAIComplianceAgent

# Configure structured logging
logger = structlog.get_logger(__name__)

class ComplianceScheduler:
    """
    Async scheduler for running compliance checks periodically without user interaction.
    Designed for Singapore-hosted Master Data Governance application.
    """
    
    def __init__(self, 
                 compliance_agent: Optional[InternationalAIComplianceAgent] = None,
                 schedule_config: Optional[dict] = None):
        """
        Initialize the compliance scheduler.
        
        Args:
            compliance_agent: The compliance agent to run
            schedule_config: Custom scheduling configuration
        """
        self.compliance_agent = compliance_agent or InternationalAIComplianceAgent()
        
        # Default schedule configuration
        self.default_config = {
            'daily_scan': {
                'enabled': True,
                'hour': 2,  # 2 AM Singapore time
                'minute': 0,
                'timezone': 'Asia/Singapore'
            },
            'weekly_deep_scan': {
                'enabled': True,
                'day_of_week': 'sun',  # Sunday
                'hour': 1,  # 1 AM Singapore time
                'minute': 0,
                'timezone': 'Asia/Singapore'
            },
            'emergency_scan_interval': {
                'enabled': False,  # Only enable during critical periods
                'hours': 6  # Every 6 hours
            }
        }
        
        self.config = schedule_config or self.default_config
        
        # Setup scheduler
        jobstores = {'default': MemoryJobStore()}
        executors = {'default': AsyncIOExecutor()}
        job_defaults = {
            'coalesce': False,
            'max_instances': 1,
            'misfire_grace_time': 300  # 5 minutes grace time
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Singapore'
        )
        
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Statistics tracking
        self.stats = {
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'last_scan_time': None,
            'last_scan_violations': 0,
            'total_violations_found': 0,
            'total_remediations_triggered': 0
        }
    
    async def initialize(self) -> bool:
        """Initialize the scheduler and compliance agent."""
        try:
            # Initialize compliance agent
            if not await self.compliance_agent.initialize():
                logger.error("Failed to initialize compliance agent")
                return False
            
            # Setup scheduled jobs
            self._setup_scheduled_jobs()
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            logger.info("Compliance scheduler initialized successfully",
                       daily_scan=self.config['daily_scan']['enabled'],
                       weekly_deep_scan=self.config['weekly_deep_scan']['enabled'],
                       timezone=self.config['daily_scan']['timezone'])
            
            return True
            
        except Exception as e:
            logger.error("Failed to initialize compliance scheduler", error=str(e))
            return False
    
    def _setup_scheduled_jobs(self):
        """Setup all scheduled compliance jobs."""
        
        # Daily compliance scan
        if self.config['daily_scan']['enabled']:
            daily_trigger = CronTrigger(
                hour=self.config['daily_scan']['hour'],
                minute=self.config['daily_scan']['minute'],
                timezone=self.config['daily_scan']['timezone']
            )
            
            self.scheduler.add_job(
                self._run_daily_compliance_scan,
                trigger=daily_trigger,
                id='daily_compliance_scan',
                name='Daily International Compliance Scan',
                replace_existing=True
            )
            
            logger.info("Scheduled daily compliance scan",
                       time=f"{self.config['daily_scan']['hour']:02d}:{self.config['daily_scan']['minute']:02d}",
                       timezone=self.config['daily_scan']['timezone'])
        
        # Weekly deep compliance scan
        if self.config['weekly_deep_scan']['enabled']:
            weekly_trigger = CronTrigger(
                day_of_week=self.config['weekly_deep_scan']['day_of_week'],
                hour=self.config['weekly_deep_scan']['hour'],
                minute=self.config['weekly_deep_scan']['minute'],
                timezone=self.config['weekly_deep_scan']['timezone']
            )
            
            self.scheduler.add_job(
                self._run_weekly_deep_scan,
                trigger=weekly_trigger,
                id='weekly_deep_compliance_scan',
                name='Weekly Deep International Compliance Scan',
                replace_existing=True
            )
            
            logger.info("Scheduled weekly deep compliance scan",
                       day=self.config['weekly_deep_scan']['day_of_week'],
                       time=f"{self.config['weekly_deep_scan']['hour']:02d}:{self.config['weekly_deep_scan']['minute']:02d}")
        
        # Emergency interval scanning (when enabled)
        if self.config['emergency_scan_interval']['enabled']:
            interval_trigger = IntervalTrigger(
                hours=self.config['emergency_scan_interval']['hours']
            )
            
            self.scheduler.add_job(
                self._run_emergency_scan,
                trigger=interval_trigger,
                id='emergency_compliance_scan',
                name='Emergency Interval Compliance Scan',
                replace_existing=True
            )
            
            logger.warning("Emergency interval scanning enabled",
                          interval_hours=self.config['emergency_scan_interval']['hours'])
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal", signal=signum)
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _run_daily_compliance_scan(self):
        """Execute daily compliance scan."""
        scan_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.info("Starting daily compliance scan", scan_id=scan_id, scan_type="daily")
            
            start_time = datetime.now()
            violations = await self.compliance_agent.scan_customer_compliance()
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self.stats['total_scans'] += 1
            self.stats['successful_scans'] += 1
            self.stats['last_scan_time'] = start_time
            self.stats['last_scan_violations'] = len(violations)
            self.stats['total_violations_found'] += len(violations)
            
            high_severity_count = sum(1 for v in violations if v.severity == 'HIGH')
            self.stats['total_remediations_triggered'] += high_severity_count
            
            logger.info("Daily compliance scan completed successfully",
                       scan_id=scan_id,
                       duration_seconds=duration,
                       violations_found=len(violations),
                       high_severity_violations=high_severity_count,
                       total_scans=self.stats['total_scans'])
            
        except Exception as e:
            self.stats['total_scans'] += 1
            self.stats['failed_scans'] += 1
            
            logger.error("Daily compliance scan failed",
                        scan_id=scan_id,
                        error=str(e),
                        failed_scans=self.stats['failed_scans'])
    
    async def _run_weekly_deep_scan(self):
        """Execute weekly deep compliance scan with extended analysis."""
        scan_id = f"weekly_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.info("Starting weekly deep compliance scan", 
                       scan_id=scan_id, 
                       scan_type="weekly_deep")
            
            start_time = datetime.now()
            
            # Run standard compliance scan
            violations = await self.compliance_agent.scan_customer_compliance()
            
            # Additional weekly analysis (if needed)
            # This could include trend analysis, pattern detection, etc.
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self.stats['total_scans'] += 1
            self.stats['successful_scans'] += 1
            self.stats['last_scan_time'] = start_time
            self.stats['last_scan_violations'] = len(violations)
            self.stats['total_violations_found'] += len(violations)
            
            high_severity_count = sum(1 for v in violations if v.severity == 'HIGH')
            self.stats['total_remediations_triggered'] += high_severity_count
            
            # Generate weekly summary
            await self._generate_weekly_summary(violations, duration)
            
            logger.info("Weekly deep compliance scan completed successfully",
                       scan_id=scan_id,
                       duration_seconds=duration,
                       violations_found=len(violations),
                       high_severity_violations=high_severity_count)
            
        except Exception as e:
            self.stats['total_scans'] += 1
            self.stats['failed_scans'] += 1
            
            logger.error("Weekly deep compliance scan failed",
                        scan_id=scan_id,
                        error=str(e))
    
    async def _run_emergency_scan(self):
        """Execute emergency compliance scan (high frequency during critical periods)."""
        scan_id = f"emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.warning("Starting emergency compliance scan", 
                          scan_id=scan_id, 
                          scan_type="emergency")
            
            start_time = datetime.now()
            violations = await self.compliance_agent.scan_customer_compliance()
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update statistics
            self.stats['total_scans'] += 1
            self.stats['successful_scans'] += 1
            
            # Emergency scans focus on high-severity violations
            high_severity_violations = [v for v in violations if v.severity == 'HIGH']
            
            if high_severity_violations:
                logger.critical("Emergency scan found high-severity violations",
                               scan_id=scan_id,
                               high_severity_count=len(high_severity_violations),
                               total_violations=len(violations))
            
            logger.warning("Emergency compliance scan completed",
                          scan_id=scan_id,
                          duration_seconds=duration,
                          violations_found=len(violations))
            
        except Exception as e:
            self.stats['total_scans'] += 1
            self.stats['failed_scans'] += 1
            
            logger.error("Emergency compliance scan failed",
                        scan_id=scan_id,
                        error=str(e))
    
    async def _generate_weekly_summary(self, violations, scan_duration):
        """Generate weekly compliance summary."""
        try:
            summary = {
                'week_ending': datetime.now().strftime('%Y-%m-%d'),
                'total_violations': len(violations),
                'violations_by_severity': {
                    'HIGH': sum(1 for v in violations if v.severity == 'HIGH'),
                    'MEDIUM': sum(1 for v in violations if v.severity == 'MEDIUM'),
                    'LOW': sum(1 for v in violations if v.severity == 'LOW')
                },
                'violations_by_framework': {
                    'PDPA': sum(1 for v in violations if v.framework == 'PDPA'),
                    'GDPR': sum(1 for v in violations if v.framework == 'GDPR')
                },
                'scan_duration_seconds': scan_duration,
                'scheduler_stats': self.stats.copy()
            }
            
            logger.info("Weekly compliance summary generated", **summary)
            
        except Exception as e:
            logger.error("Failed to generate weekly summary", error=str(e))
    
    async def start(self):
        """Start the compliance scheduler."""
        try:
            if self.running:
                logger.warning("Scheduler already running")
                return
            
            self.scheduler.start()
            self.running = True
            
            logger.info("International compliance scheduler started",
                       jobs_count=len(self.scheduler.get_jobs()),
                       next_run_time=self.scheduler.get_jobs()[0].next_run_time if self.scheduler.get_jobs() else None)
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error("Scheduler startup failed", error=str(e))
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown of the scheduler."""
        try:
            logger.info("Shutting down compliance scheduler...")
            
            if self.running and self.scheduler.running:
                self.scheduler.shutdown(wait=True)
            
            await self.compliance_agent.cleanup()
            self.running = False
            self.shutdown_event.set()
            
            logger.info("Compliance scheduler shutdown completed",
                       final_stats=self.stats)
            
        except Exception as e:
            logger.error("Error during scheduler shutdown", error=str(e))
    
    def get_status(self) -> dict:
        """Get current scheduler status and statistics."""
        return {
            'running': self.running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ],
            'statistics': self.stats.copy()
        }
    
    async def run_manual_scan(self) -> dict:
        """Run a manual compliance scan (for testing/debugging)."""
        try:
            logger.info("Starting manual compliance scan")
            
            start_time = datetime.now()
            violations = await self.compliance_agent.scan_customer_compliance()
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                'scan_time': start_time.isoformat(),
                'duration_seconds': duration,
                'violations_found': len(violations),
                'violations_by_severity': {
                    'HIGH': sum(1 for v in violations if v.severity == 'HIGH'),
                    'MEDIUM': sum(1 for v in violations if v.severity == 'MEDIUM'),
                    'LOW': sum(1 for v in violations if v.severity == 'LOW')
                }
            }
            
            logger.info("Manual compliance scan completed", **result)
            return result
            
        except Exception as e:
            logger.error("Manual compliance scan failed", error=str(e))
            return {'error': str(e)}

async def main():
    """Main function to run the compliance scheduler."""
    print("🕐 Starting International AI Compliance Scheduler")
    print("=" * 60)
    print("This scheduler runs automatically without user interaction")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    scheduler = ComplianceScheduler()
    
    try:
        # Initialize
        if not await scheduler.initialize():
            print("❌ Failed to initialize scheduler")
            return
        
        print("✅ Scheduler initialized successfully")
        print(f"📊 Current status: {scheduler.get_status()}")
        
        # Start scheduler (runs until interrupted)
        await scheduler.start()
        
    except KeyboardInterrupt:
        print("\n⏹️  Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Scheduler error: {str(e)}")
    finally:
        await scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())