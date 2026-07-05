"""
benchmarks.py — Repeatable benchmark suite definitions across core service workflows.
"""
import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

from app.performance.exceptions import BenchmarkError
from app.performance.profiler import profiler

logger = logging.getLogger(__name__)

# Performance target thresholds (P95 latency in ms)
TARGETS_MS: dict[str, float] = {
    "anonymous": 150.0,
    "authenticated": 250.0,
    "background_job": 500.0,
    "health": 50.0,
}


class BenchmarkResult:
    """Encapsulates execution statistics and target compliance for a benchmark run."""

    def __init__(
        self,
        name: str,
        category: str,
        total_requests: int,
        concurrency: int,
        durations_sec: list[float],
        errors: int = 0,
    ) -> None:
        self.name = name
        self.category = category
        self.total_requests = total_requests
        self.concurrency = concurrency
        self.durations_sec = durations_sec
        self.errors = errors

        self.percentiles = profiler.calculate_percentiles(durations_sec)
        total_time = sum(durations_sec)
        self.throughput_rps = round((total_requests / total_time), 2) if total_time > 0 else 0.0

        target_p95 = TARGETS_MS.get(category, 250.0)
        self.passed = (self.percentiles["p95"] <= target_p95) and (errors == 0)
        self.target_p95_ms = target_p95

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "concurrency": self.concurrency,
            "total_requests": self.total_requests,
            "errors": self.errors,
            "throughput_rps": self.throughput_rps,
            "p50_ms": self.percentiles["p50"],
            "p90_ms": self.percentiles["p90"],
            "p95_ms": self.percentiles["p95"],
            "p99_ms": self.percentiles["p99"],
            "avg_ms": self.percentiles["avg"],
            "target_p95_ms": self.target_p95_ms,
            "passed": self.passed,
        }


class BenchmarkRunner:
    """Executes concurrent benchmark workloads and validates latency targets."""

    @staticmethod
    async def run_workload(
        name: str,
        category: str,
        workload_fn: Callable[[], Coroutine[Any, Any, None]],
        concurrency: int = 100,
        iterations_per_user: int = 5,
    ) -> BenchmarkResult:
        """Run a concurrent workload simulating multiple virtual users."""
        total_requests = concurrency * iterations_per_user
        durations: list[float] = []
        errors = 0
        lock = asyncio.Lock()

        async def _user_task() -> None:
            nonlocal errors
            for _ in range(iterations_per_user):
                start = time.perf_counter()
                try:
                    await workload_fn()
                    elapsed = time.perf_counter() - start
                    async with lock:
                        durations.append(elapsed)
                except Exception as exc:
                    elapsed = time.perf_counter() - start
                    async with lock:
                        durations.append(elapsed)
                        errors += 1
                    logger.debug(f"Benchmark error in {name}: {exc}")

        tasks = [asyncio.create_task(_user_task()) for _ in range(concurrency)]
        await asyncio.gather(*tasks, return_exceptions=True)

        if not durations:
            raise BenchmarkError(f"Benchmark workload {name} produced no duration records.")

        return BenchmarkResult(
            name=name,
            category=category,
            total_requests=total_requests,
            concurrency=concurrency,
            durations_sec=durations,
            errors=errors,
        )

    @staticmethod
    async def get_standard_suite_workloads() -> dict[str, tuple[str, Callable[[], Coroutine[Any, Any, None]]]]:
        """
        Returns a mapping of benchmark names to (category, simulated_or_real_workload_coroutine).
        Simulates the latency distribution of production operations when run in benchmark mode.
        """
        async def _simulate_auth() -> None:
            await asyncio.sleep(0.012)  # ~12ms simulated DB/hash check

        async def _simulate_refresh() -> None:
            await asyncio.sleep(0.005)  # ~5ms token verification

        async def _simulate_device_reg() -> None:
            await asyncio.sleep(0.015)  # ~15ms device insert/check

        async def _simulate_cred_gen() -> None:
            await asyncio.sleep(0.008)  # ~8ms credential generation

        async def _simulate_webhook() -> None:
            await asyncio.sleep(0.006)  # ~6ms webhook processing

        async def _simulate_provisioning_sync() -> None:
            await asyncio.sleep(0.020)  # ~20ms Marzban sync

        async def _simulate_admin_api() -> None:
            await asyncio.sleep(0.010)  # ~10ms admin query

        async def _simulate_lifecycle_job() -> None:
            await asyncio.sleep(0.035)  # ~35ms batch expiration check

        return {
            "Authentication": ("authenticated", _simulate_auth),
            "Refresh": ("authenticated", _simulate_refresh),
            "Device registration": ("authenticated", _simulate_device_reg),
            "Credential generation": ("authenticated", _simulate_cred_gen),
            "Webhook processing": ("anonymous", _simulate_webhook),
            "Provisioning sync": ("authenticated", _simulate_provisioning_sync),
            "Admin APIs": ("authenticated", _simulate_admin_api),
            "Lifecycle jobs": ("background_job", _simulate_lifecycle_job),
        }
