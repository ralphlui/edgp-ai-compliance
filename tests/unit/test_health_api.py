from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.compliance_agent.api import health as health_module
from config.settings import settings


@pytest.fixture
def health_app():
    app = FastAPI()
    app.include_router(health_module.router)
    return TestClient(app)


def test_health_check_returns_status(health_app, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "1.2.3")
    monkeypatch.setattr(settings, "environment", "test")

    response = health_app.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == "1.2.3"


def test_readiness_check_unready_without_secrets(health_app, monkeypatch):
    monkeypatch.setattr(settings, "enable_ai_analysis", True)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "remediation_agent_enabled", True)
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings.__class__, "is_production", lambda self: True)
    monkeypatch.setattr(settings.__class__, "validate_required_secrets", lambda self: ["MISSING"])

    response = health_app.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["checks"]["openai"] is False
    assert payload["checks"]["aws"] is False


def test_liveness_check_handles_resource_thresholds(monkeypatch, health_app):
    fake_psutil = SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(percent=99.0),
        cpu_percent=lambda interval=0.1: 12.0,
    )
    monkeypatch.setattr(health_module, "psutil", fake_psutil)

    response = health_app.get("/health/live")

    assert response.status_code == 503
    payload = response.json()
    assert payload["alive"] is False
    assert payload["memory_usage_percent"] == 99.0
