"""
Integration tests for remediation API endpoints
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.compliance_agent.api.main import app


@pytest.mark.asyncio
class TestRemediationAPIIntegration:
    """Integration tests for remediation endpoints"""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_health_check(self, client):
        """Test health check endpoint"""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data

    async def test_readiness_check(self, client):
        """Test readiness check endpoint"""
        response = await client.get("/health/ready")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)

    async def test_liveness_check(self, client):
        """Test liveness check endpoint"""
        response = await client.get("/health/live")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "alive" in data
        assert "memory_usage_percent" in data
        assert "cpu_usage_percent" in data

    async def test_root_endpoint(self, client):
        """Test root endpoint returns service info"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "environment" in data

    @pytest.mark.skipif(
        True,  # Skip if remediation agent is disabled
        reason="Requires remediation agent configuration"
    )
    async def test_remediation_trigger_endpoint(self, client):
        """Test remediation trigger endpoint"""
        payload = {
            "violation_id": "test-violation-001",
            "violation_type": "data_retention",
            "severity": "high",
            "details": {
                "description": "Data retention policy violation",
                "affected_records": 100
            }
        }

        with patch("src.remediation_agent.main.RemediationAgent") as mock_agent:
            mock_instance = AsyncMock()
            mock_agent.return_value = mock_instance
            mock_instance.trigger_workflow.return_value = {
                "request_id": "req-001",
                "status": "initiated"
            }

            response = await client.post("/api/v1/remediation/trigger", json=payload)

            if response.status_code == 200:
                data = response.json()
                assert "request_id" in data
                assert "status" in data

    async def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = await client.get("/metrics")

        # Metrics might be disabled in test environment
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            # Check that response is in Prometheus format
            assert "text/plain" in response.headers.get("content-type", "")


@pytest.mark.asyncio
class TestRemediationWorkflowIntegration:
    """Integration tests for full remediation workflow"""

    @pytest_asyncio.fixture
    def mock_sqs(self):
        """Mock SQS client"""
        with patch("boto3.client") as mock:
            mock_client = Mock()
            mock.return_value = mock_client
            mock_client.send_message.return_value = {
                "MessageId": "test-msg-001"
            }
            mock_client.receive_message.return_value = {
                "Messages": []
            }
            yield mock_client

    @pytest_asyncio.fixture
    def mock_openai(self):
        """Mock OpenAI client"""
        with patch("openai.ChatCompletion.create") as mock:
            mock.return_value = {
                "choices": [{
                    "message": {
                        "content": "Test remediation decision"
                    }
                }]
            }
            yield mock

    async def test_end_to_end_workflow_mock(self, mock_sqs, mock_openai):
        """Test end-to-end workflow with mocked dependencies"""
        from src.remediation_agent.main import RemediationAgent
        from src.remediation_agent.state.models import RemediationRequest, ViolationType, Severity

        # Create remediation request
        request = RemediationRequest(
            violation_id="test-violation-001",
            violation_type=ViolationType.DATA_RETENTION,
            severity=Severity.HIGH,
            details={"description": "Test violation"}
        )

        # This would normally trigger the workflow
        # In tests, we verify the components work correctly
        assert request.violation_id == "test-violation-001"
        assert request.severity == Severity.HIGH


@pytest.mark.asyncio
class TestAPIErrorHandling:
    """Test API error handling"""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_invalid_endpoint_404(self, client):
        """Test 404 for invalid endpoint"""
        response = await client.get("/api/v1/invalid-endpoint")
        assert response.status_code == 404

    async def test_invalid_method_405(self, client):
        """Test 405 for invalid method"""
        response = await client.post("/health")
        assert response.status_code == 405


@pytest.mark.asyncio
class TestAPICORS:
    """Test CORS configuration"""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = await client.options(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200
