"""
app/observability/metrics.py — Internal Metrics Registry & Prometheus Export (Phase 3.2.5 & 3.2.6).
Thread-safe internal metrics service tracking HTTP, Authentication, Payments, Provisioning,
Scheduler, Database, and Exception metrics without coupling to external monitoring daemons.
Exposes standard Prometheus text formatting for `/metrics` endpoints.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Mapping


class MetricsRegistry:
    """
    In-memory metrics registry tracking counters, gauges, and summaries.
    Strictly passive: failures in metrics reporting never raise exceptions to callers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(lambda: defaultdict(float))
        self._summaries: dict[str, dict[tuple[tuple[str, str], ...], dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"count": 0.0, "sum": 0.0})
        )
        self._descriptions: dict[str, tuple[str, str]] = {}
        self._init_default_descriptions()

    def _init_default_descriptions(self) -> None:
        self.register_metric("http_requests_total", "counter", "Total HTTP requests processed.")
        self.register_metric("http_requests_active", "gauge", "Currently active HTTP requests.")
        self.register_metric("http_request_duration_ms", "summary", "HTTP request latency in milliseconds.")
        self.register_metric("http_errors_total", "counter", "Total HTTP error responses (4xx/5xx).")

        self.register_metric("auth_logins_total", "counter", "Total login attempts.")
        self.register_metric("auth_token_refreshes_total", "counter", "Total token refresh attempts.")
        self.register_metric("auth_failures_total", "counter", "Total authentication failures.")

        self.register_metric("payments_successful_total", "counter", "Total successful payment transactions.")
        self.register_metric("payments_failed_total", "counter", "Total failed payment transactions.")
        self.register_metric("webhooks_delivered_total", "counter", "Total payment webhook notifications processed.")

        self.register_metric("provisioning_successful_total", "counter", "Total successful provisioning operations.")
        self.register_metric("provisioning_retries_total", "counter", "Total provisioning operations queued for retry.")
        self.register_metric("provisioning_failures_total", "counter", "Total permanent provisioning failures.")

        self.register_metric("scheduler_jobs_executed_total", "counter", "Total background scheduled job executions.")
        self.register_metric("scheduler_job_duration_ms", "summary", "Background scheduled job execution time in ms.")
        self.register_metric("scheduler_job_failures_total", "counter", "Total background scheduled job failures.")

        self.register_metric("db_queries_total", "counter", "Total database queries executed.")
        self.register_metric("db_transaction_failures_total", "counter", "Total database transaction rollback failures.")
        self.register_metric("exceptions_total", "counter", "Total unhandled or mapped exceptions by type.")

        self.register_metric("rate_limit_hits_total", "counter", "Total rate limit checks performed.")
        self.register_metric("rate_limit_denied_total", "counter", "Total rate limit checks denied (HTTP 429).")
        self.register_metric("rate_limit_active_keys", "gauge", "Number of currently active rate limit tracking keys.")
        self.register_metric("rate_limit_backend_errors", "counter", "Total rate limit storage backend errors.")

    def register_metric(self, name: str, metric_type: str, help_text: str) -> None:
        with self._lock:
            self._descriptions[name] = (metric_type, help_text)

    def _to_key(self, labels: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
        if not labels:
            return ()
        # Sort labels by key for deterministic tuple representation
        return tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def inc_counter(self, name: str, value: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        try:
            if value < 0:
                return
            key = self._to_key(labels)
            with self._lock:
                self._counters[name][key] += value
        except Exception:
            pass

    def set_gauge(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        try:
            key = self._to_key(labels)
            with self._lock:
                self._gauges[name][key] = float(value)
        except Exception:
            pass

    def inc_gauge(self, name: str, delta: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        try:
            key = self._to_key(labels)
            with self._lock:
                self._gauges[name][key] += float(delta)
        except Exception:
            pass

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        try:
            key = self._to_key(labels)
            with self._lock:
                target = self._summaries[name][key]
                target["count"] += 1.0
                target["sum"] += float(value)
        except Exception:
            pass

    def get_summary(self) -> dict[str, Any]:
        """Return a JSON-friendly summary dictionary for Admin `/health` endpoint inspections."""
        with self._lock:
            summary: dict[str, Any] = {}
            for name, data in self._counters.items():
                total = sum(data.values())
                summary[name] = total
            for name, data in self._gauges.items():
                total = sum(data.values())
                summary[name] = total
            for name, data in self._summaries.items():
                total_count = sum(d["count"] for d in data.values())
                total_sum = sum(d["sum"] for d in data.values())
                avg = round(total_sum / total_count, 2) if total_count > 0 else 0.0
                summary[name] = {"count": total_count, "sum": round(total_sum, 2), "avg_ms": avg}
            return summary

    def to_prometheus_text(self) -> str:
        """Export metrics in standard Prometheus text format (version 0.0.4)."""
        lines: list[str] = []
        with self._lock:
            for name, (m_type, help_text) in sorted(self._descriptions.items()):
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {m_type}")

                if m_type == "counter":
                    data = self._counters.get(name, {})
                    if not data:
                        lines.append(f"{name} 0")
                    else:
                        for key, val in sorted(data.items()):
                            label_str = self._format_labels(key)
                            lines.append(f"{name}{label_str} {val}")

                elif m_type == "gauge":
                    data = self._gauges.get(name, {})
                    if not data:
                        lines.append(f"{name} 0")
                    else:
                        for key, val in sorted(data.items()):
                            label_str = self._format_labels(key)
                            lines.append(f"{name}{label_str} {val}")

                elif m_type == "summary":
                    data = self._summaries.get(name, {})
                    if not data:
                        lines.append(f"{name}_count 0")
                        lines.append(f"{name}_sum 0")
                    else:
                        for key, val in sorted(data.items()):
                            label_str = self._format_labels(key)
                            lines.append(f"{name}_count{label_str} {val['count']}")
                            lines.append(f"{name}_sum{label_str} {round(val['sum'], 2)}")
                lines.append("")
        return "\n".join(lines)

    def _format_labels(self, key: tuple[tuple[str, str], ...]) -> str:
        if not key:
            return ""
        pairs = [f'{k}="{self._escape_label(v)}"' for k, v in key]
        return "{" + ", ".join(pairs) + "}"

    def _escape_label(self, val: str) -> str:
        return val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def reset(self) -> None:
        """Clear all metrics data (useful for test isolation)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._summaries.clear()


metrics_registry = MetricsRegistry()
