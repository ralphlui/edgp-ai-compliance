"""
Prometheus metrics endpoints and collectors
"""

from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry
import time

from config.settings import settings

router = APIRouter(tags=["Metrics"])

# Create a custom registry
registry = CollectorRegistry()

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    registry=registry
)

# Business metrics
compliance_checks_total = Counter(
    "compliance_checks_total",
    "Total compliance checks performed",
    ["framework", "status"],
    registry=registry
)

remediation_workflows_total = Counter(
    "remediation_workflows_total",
    "Total remediation workflows",
    ["status"],
    registry=registry
)

remediation_workflows_active = Gauge(
    "remediation_workflows_active",
    "Active remediation workflows",
    registry=registry
)

ai_api_calls_total = Counter(
    "ai_api_calls_total",
    "Total AI API calls",
    ["model", "status"],
    registry=registry
)

ai_api_latency_seconds = Histogram(
    "ai_api_latency_seconds",
    "AI API call latency",
    ["model"],
    registry=registry
)

# System metrics
system_memory_usage_bytes = Gauge(
    "system_memory_usage_bytes",
    "System memory usage in bytes",
    registry=registry
)

system_cpu_usage_percent = Gauge(
    "system_cpu_usage_percent",
    "System CPU usage percentage",
    registry=registry
)


@router.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus exposition format
    """
    if not settings.metrics_enabled:
        return Response(
            content="Metrics collection is disabled",
            status_code=404
        )

    # Update system metrics
    try:
        import psutil
        system_memory_usage_bytes.set(psutil.virtual_memory().used)
        system_cpu_usage_percent.set(psutil.cpu_percent(interval=0.1))
    except ImportError:
        pass

    metrics_output = generate_latest(registry)
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )


class MetricsMiddleware:
    """Middleware to collect HTTP metrics"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Wrap send to capture status code
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Record metrics
            duration = time.time() - start_time
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()
            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)


def record_compliance_check(framework: str, status: str) -> None:
    """Record a compliance check"""
    compliance_checks_total.labels(framework=framework, status=status).inc()


def record_remediation_workflow(status: str) -> None:
    """Record a remediation workflow"""
    remediation_workflows_total.labels(status=status).inc()


def update_active_workflows(count: int) -> None:
    """Update active workflow count"""
    remediation_workflows_active.set(count)


def record_ai_call(model: str, status: str, duration: float) -> None:
    """Record an AI API call"""
    ai_api_calls_total.labels(model=model, status=status).inc()
    ai_api_latency_seconds.labels(model=model).observe(duration)
