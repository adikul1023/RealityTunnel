"""
test_observability.py — Automated test suite for Phase 3.2 Observability & Monitoring.

Covers:
  1. Request ID generation and X-Request-ID reuse.
  2. Correlation context propagation.
  3. Structured JSON log formatting and schema.
  4. Secret redaction within structured JSON log output.
  5. Metrics registry increments across domains.
  6. Prometheus endpoint formatting (GET /metrics) and auth rules.
  7. Slow request detection warning log generation.
  8. Health endpoint expansion (anonymous vs. admin response schema differentiation).
  9. Middleware ordering and X-Response-Time header injection.
  10. OpenTelemetry No-Op tracer behavior.
  11. Log sampling rate rules (error logs are never sampled).
  12. Background job metrics tracking.
"""
import json
import logging
import pytest
from unittest.mock import patch, MagicMock

from app.config import settings
from app.observability import (
    bind_context,
    clear_context,
    get_component,
    get_correlation_id,
    get_operation,
    get_request_id,
    set_correlation_id,
    set_request_id,
    metrics_registry,
    StructuredJsonFormatter,
    LogSamplingFilter,
    get_tracer,
)
from app.observability.middleware import record_exception_metric


@pytest.fixture(autouse=True)
def reset_metrics():
    metrics_registry.reset()
    clear_context()
    yield
    metrics_registry.reset()
    clear_context()


# ── 1. Request ID & Header Reuse ─────────────────────────────────────────────
async def test_request_id_generation_and_reuse(async_client):
    # Test auto-generated X-Request-ID
    resp1 = await async_client.get("/version")
    assert resp1.status_code == 200
    req_id_1 = resp1.headers.get("X-Request-ID")
    assert req_id_1 and len(req_id_1) >= 32
    assert resp1.headers.get("X-Response-Time")

    # Test reuse of supplied X-Request-ID
    custom_id = "test-custom-req-id-12345"
    resp2 = await async_client.get("/version", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Request-ID") == custom_id


# ── 2. Correlation Context Propagation ───────────────────────────────────────
def test_correlation_context_propagation():
    clear_context()
    assert get_request_id() == ""
    assert get_correlation_id() == ""

    tokens = bind_context(
        request_id="req-root",
        correlation_id="corr-chain-999",
        component="webhook",
        operation="process_payment",
    )
    assert get_request_id() == "req-root"
    assert get_correlation_id() == "corr-chain-999"
    assert get_component() == "webhook"
    assert get_operation() == "process_payment"

    # Simulate inner function modifying component
    tokens2 = bind_context(component="subscription")
    assert get_component() == "subscription"
    assert get_correlation_id() == "corr-chain-999"

    clear_context()
    assert get_correlation_id() == ""


# ── 3. Structured JSON Log Formatting & Schema ───────────────────────────────
def test_structured_json_formatter_schema():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="app.services.payment",
        level=logging.INFO,
        pathname="payment.py",
        lineno=10,
        msg="Payment processed successfully for order %s",
        args=("order_123",),
        exc_info=None,
    )
    record.duration_ms = 45.67
    record.status = "ok"

    bind_context(request_id="req-log-1", correlation_id="corr-log-1", component="payment", operation="charge")
    output = formatter.format(record)
    clear_context()

    data = json.loads(output)
    assert data["timestamp"]
    assert data["level"] == "INFO"
    assert data["service"] == "RealityTunnel"
    assert data["environment"] == settings.environment
    assert data["request_id"] == "req-log-1"
    assert data["correlation_id"] == "corr-log-1"
    assert data["component"] == "payment"
    assert data["operation"] == "charge"
    assert data["duration_ms"] == 45.67
    assert data["status"] == "ok"
    assert data["message"] == "Payment processed successfully for order order_123"


# ── 4. Secret Redaction Within Structured JSON Logs ──────────────────────────
def test_structured_json_formatter_secret_redaction():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="Failed database connection to postgresql://admin:SecretPass123@db.internal:5432/db with token=xyz987token",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert "SecretPass123" not in output
    assert "xyz987token" not in output
    assert "***REDACTED***" in output
    # Verify it remains valid JSON after redaction
    data = json.loads(output)
    assert "***REDACTED***" in data["message"]


# ── 5. Metrics Registry Increments Across Domains ────────────────────────────
def test_metrics_registry_increments():
    metrics_registry.inc_counter("http_requests_total", 1.0, {"method": "GET", "route": "/test", "status": "200"})
    metrics_registry.inc_counter("auth_logins_total", 1.0, {"status": "success"})
    metrics_registry.inc_counter("payments_successful_total", 1.0)
    metrics_registry.observe("http_request_duration_ms", 12.5, {"method": "GET", "route": "/test"})

    summary = metrics_registry.get_summary()
    assert summary["http_requests_total"] == 1.0
    assert summary["auth_logins_total"] == 1.0
    assert summary["payments_successful_total"] == 1.0
    assert summary["http_request_duration_ms"]["count"] == 1.0
    assert summary["http_request_duration_ms"]["sum"] == 12.5
    assert summary["http_request_duration_ms"]["avg_ms"] == 12.5


# ── 6. Prometheus Endpoint Formatting & Auth Rules ───────────────────────────
async def test_prometheus_endpoint(async_client, admin_auth_headers_factory):
    metrics_registry.inc_counter("http_requests_total", 5.0, {"method": "POST", "route": "/api/test", "status": "201"})
    
    # Test unauthenticated access when metrics_auth_required is False
    with patch.object(settings, "metrics_auth_required", False):
        resp_anon = await async_client.get("/metrics")
        assert resp_anon.status_code == 200
        text = resp_anon.text
        assert "# HELP http_requests_total" in text
        assert "# TYPE http_requests_total counter" in text
        assert 'http_requests_total{method="POST", route="/api/test", status="201"} 5.0' in text

    # Test authentication enforced when metrics_auth_required is True
    with patch.object(settings, "metrics_auth_required", True):
        resp_unauth = await async_client.get("/metrics")
        assert resp_unauth.status_code == 401

        headers, _ = await admin_auth_headers_factory(is_super_admin=False, username="metrics_admin")
        resp_auth = await async_client.get("/metrics", headers=headers)
        assert resp_auth.status_code == 200


# ── 7. Slow Request Detection Warning Log ────────────────────────────────────
async def test_slow_request_detection_warning(async_client, caplog):
    # Set slow request threshold to a very small number (e.g. 0.01 ms)
    with patch.object(settings, "slow_request_threshold_ms", 0.001):
        with caplog.at_level(logging.WARNING):
            resp = await async_client.get("/version")
            assert resp.status_code == 200
            slow_logs = [r for r in caplog.records if "Slow request detected" in r.getMessage()]
            assert len(slow_logs) >= 1
            assert slow_logs[0].levelno == logging.WARNING
            assert not slow_logs[0].exc_info  # No stack trace for slow requests


# ── 8. Health Endpoint Expansion (Anonymous vs. Admin) ───────────────────────
async def test_health_endpoint_expansion(async_client, admin_auth_headers_factory):
    # Anonymous call receives only basic fields
    resp_anon = await async_client.get("/health")
    assert resp_anon.status_code == 200
    data_anon = resp_anon.json()
    assert data_anon["status"] in ("ok", "degraded")
    assert data_anon["database"]
    assert data_anon["version"]
    assert data_anon.get("fingerprint") is None
    assert data_anon.get("scheduler") is None
    assert data_anon.get("metrics_summary") is None

    # Admin call receives expanded observability fields
    headers, _ = await admin_auth_headers_factory(is_super_admin=False, username="health_admin_obs")
    resp_admin = await async_client.get("/health", headers=headers)
    assert resp_admin.status_code == 200
    data_admin = resp_admin.json()
    assert data_admin.get("fingerprint") is not None
    assert data_admin.get("scheduler") is not None
    assert data_admin["scheduler"]["status"] in ("running", "stopped", "not_initialized")
    assert data_admin.get("provider_health") is not None
    assert data_admin.get("metrics_summary") is not None


# ── 9. Middleware Ordering & Response Timing ─────────────────────────────────
async def test_middleware_timing_header(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "X-Response-Time" in resp.headers
    assert resp.headers["X-Response-Time"].endswith("ms")


# ── 10. OpenTelemetry No-Op Tracer Behavior ──────────────────────────────────
def test_opentelemetry_noop_tracer():
    tracer = get_tracer()
    with tracer.start_span("test.operation", {"custom.attr": "val"}) as span:
        span.set_attribute("status", "ok")
        span.set_status("OK")
    assert span.attributes["custom.attr"] == "val"
    assert span.attributes["status"] == "ok"
    assert span.status == "OK"


# ── 11. Log Sampling Rate Rules ──────────────────────────────────────────────
def test_log_sampling_rules():
    filter_10pct = LogSamplingFilter(sampling_rate=0.0)
    
    # Normal info log should be sampled out when rate=0.0
    info_record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg="test info", args=(), exc_info=None
    )
    assert filter_10pct.filter(info_record) is False

    # Error logs must NEVER be sampled out
    err_record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0, msg="test error", args=(), exc_info=None
    )
    assert filter_10pct.filter(err_record) is True

    # Forced sample record should not be sampled out
    forced_record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg="test force", args=(), exc_info=None
    )
    forced_record.force_sample = True
    assert filter_10pct.filter(forced_record) is True


# ── 12. Background Job Metrics Tracking ──────────────────────────────────────
async def test_background_job_metrics_tracking():
    from app.scheduler import JobScheduler
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from unittest.mock import AsyncMock

    mock_session_factory = MagicMock(spec=async_sessionmaker)
    scheduler = JobScheduler(mock_session_factory)
    scheduler.start()

    stats_init = scheduler.get_job_stats()
    assert "failed_provision_retry" in stats_init
    assert stats_init["failed_provision_retry"]["execution_count"] == 0

    await scheduler.stop()
