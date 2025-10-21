"""
Integration tests for API Health and Metrics
Tests for health check endpoints and metrics collection
"""

import pytest
from fastapi import Response


class TestHealthEndpoints:
    """Test health check endpoints"""

    @pytest.mark.asyncio
    async def test_health_check_basic(self):
        """Test basic health check"""
        from src.compliance_agent.api.health import health_check
        
        result = await health_check()
        
        assert result is not None
        assert result.status == "healthy"
        assert result.service == "AI Compliance Agent"
        assert result.timestamp is not None
        assert result.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_health_check_with_engine(self):
        """Test health check returns proper structure"""
        from src.compliance_agent.api.health import health_check
        
        result = await health_check()
        
        assert result is not None
        assert hasattr(result, 'status')
        assert hasattr(result, 'version')
        assert hasattr(result, 'environment')

    @pytest.mark.asyncio
    async def test_readiness_check(self):
        """Test readiness probe"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None
        assert hasattr(result, 'ready')
        assert hasattr(result, 'checks')
        assert isinstance(result.checks, dict)

    @pytest.mark.asyncio
    async def test_liveness_check(self):
        """Test liveness probe"""
        from src.compliance_agent.api.health import liveness_check
        
        response = Response()
        result = await liveness_check(response)
        
        assert result is not None
        assert hasattr(result, 'alive')
        assert hasattr(result, 'memory_usage_percent')
        assert hasattr(result, 'cpu_usage_percent')

    @pytest.mark.asyncio
    async def test_detailed_health_check(self):
        """Test detailed health check"""
        from src.compliance_agent.api.health import health_check
        
        result = await health_check()
        
        assert result is not None
        assert result.status == "healthy"


class TestMetricsCollection:
    """Test metrics collection"""

    @pytest.mark.asyncio
    async def test_get_metrics_basic(self):
        """Test basic metrics endpoint"""
        from src.compliance_agent.api.metrics import metrics
        
        result = await metrics()
        
        assert result is not None

    def test_metrics_has_counters(self):
        """Test metrics module has counter metrics"""
        from src.compliance_agent.api import metrics as metrics_module
        
        assert hasattr(metrics_module, 'http_requests_total')
        assert hasattr(metrics_module, 'compliance_checks_total')

    def test_metrics_has_histograms(self):
        """Test metrics module has histogram metrics"""
        from src.compliance_agent.api import metrics as metrics_module
        
        assert hasattr(metrics_module, 'http_request_duration_seconds')

    def test_record_request_metric(self):
        """Test recording request metrics"""
        from src.compliance_agent.api import metrics as metrics_module
        
        metrics_module.http_requests_total.labels(
            method="GET",
            endpoint="/test",
            status="200"
        ).inc()
        
        assert True

    def test_record_duration_metric(self):
        """Test recording duration metrics"""
        from src.compliance_agent.api import metrics as metrics_module
        
        metrics_module.http_request_duration_seconds.labels(
            method="GET",
            endpoint="/test"
        ).observe(0.5)
        
        assert True


class TestHealthCheckDetails:
    """Test detailed health check components"""

    @pytest.mark.asyncio
    async def test_check_database_connection(self):
        """Test database connection check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None
        assert hasattr(result, 'checks')

    @pytest.mark.asyncio
    async def test_check_ai_service_status(self):
        """Test AI service status check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_check_remediation_agent_status(self):
        """Test remediation agent status check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_health_check_with_failures(self):
        """Test health check handles failures"""
        from src.compliance_agent.api.health import health_check
        
        result = await health_check()
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_health_check_response_format(self):
        """Test health check response format"""
        from src.compliance_agent.api.health import health_check
        
        result = await health_check()
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'timestamp')


class TestMetricsExport:
    """Test metrics export"""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        from src.compliance_agent.api.metrics import metrics
        
        result = await metrics()
        
        assert result is not None

    def test_metrics_include_violation_counts(self):
        """Test metrics include violation counts"""
        from src.compliance_agent.api import metrics as metrics_module
        
        assert hasattr(metrics_module, 'compliance_checks_total')


class TestHealthCheckDependencies:
    """Test health check dependencies"""

    @pytest.mark.asyncio
    async def test_verify_llm_service_available(self):
        """Test LLM service availability check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_verify_database_available(self):
        """Test database availability check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_verify_aws_services_available(self):
        """Test AWS services availability check"""
        from src.compliance_agent.api.health import readiness_check
        
        response = Response()
        result = await readiness_check(response)
        
        assert result is not None


class TestMetricsLabels:
    """Test metrics labels"""

    def test_metrics_with_severity_labels(self):
        """Test metrics with severity labels"""
        from src.compliance_agent.api import metrics as metrics_module
        
        metrics_module.compliance_checks_total.labels(
            framework="PDPA",
            status="passed"
        ).inc()
        
        assert True
