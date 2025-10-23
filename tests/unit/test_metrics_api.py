from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Response
from starlette.testclient import TestClient

from src.compliance_agent.api import metrics as metrics_module
from src.compliance_agent.api.metrics import (
    MetricsMiddleware,
    record_ai_call,
    record_compliance_check,
    record_remediation_workflow,
    update_active_workflows,
    router as metrics_router,
)
from config.settings import settings


def test_metrics_endpoint_disabled(monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", False)
    app = FastAPI()
    app.include_router(metrics_router)
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 404
    assert response.text == "Metrics collection is disabled"


def test_metrics_endpoint_emits_prometheus(monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    fake_psutil = SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(used=12345),
        cpu_percent=lambda interval=0.1: 42.0,
    )
    monkeypatch.setattr(metrics_module, "psutil", fake_psutil, raising=False)

    app = FastAPI()
    app.include_router(metrics_router)
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text


@pytest.mark.asyncio
async def test_metrics_middleware_records(monkeypatch):
    captured = {}

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = MetricsMiddleware(app)
    scope = {"type": "http", "method": "GET", "path": "/example"}

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        captured.setdefault("messages", []).append(message)

    await middleware(scope, receive, send)

    samples = metrics_module.http_requests_total.collect()[0].samples
    assert any(sample.labels["endpoint"] == "/example" for sample in samples)


def test_metric_helpers_increment_counters():
    before = metrics_module.compliance_checks_total.labels(
        framework="gdpr",
        status="success",
    )._value.get()
    record_compliance_check("gdpr", "success")
    after = metrics_module.compliance_checks_total.labels(
        framework="gdpr",
        status="success",
    )._value.get()
    assert after == before + 1

    before_remediation = metrics_module.remediation_workflows_total.labels(
        status="completed"
    )._value.get()
    record_remediation_workflow("completed")
    after_remediation = metrics_module.remediation_workflows_total.labels(
        status="completed"
    )._value.get()
    assert after_remediation == before_remediation + 1

    update_active_workflows(7)
    assert metrics_module.remediation_workflows_active._value.get() == 7

    before_ai = metrics_module.ai_api_calls_total.labels(
        model="gpt", status="ok"
    )._value.get()
    record_ai_call("gpt", "ok", duration=0.5)
    after_ai = metrics_module.ai_api_calls_total.labels(
        model="gpt", status="ok"
    )._value.get()
    assert after_ai == before_ai + 1
