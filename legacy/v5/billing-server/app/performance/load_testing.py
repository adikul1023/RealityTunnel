"""
load_testing.py — Concurrent virtual user load testing engine and report generator.
"""
import logging
from typing import Any

from app.performance.benchmarks import BenchmarkRunner
from app.performance.exceptions import BenchmarkError

logger = logging.getLogger(__name__)


class LoadTestSuite:
    """Orchestrates multi-concurrency load test execution across benchmark workloads."""

    def __init__(self, concurrency_levels: tuple[int, ...] = (100, 250, 500, 1000)) -> None:
        self.concurrency_levels = concurrency_levels
        self.results: list[dict[str, Any]] = []

    async def execute_all(self, iterations_per_user: int = 2) -> list[dict[str, Any]]:
        """Run all standard benchmark workloads across specified concurrency levels."""
        self.results.clear()
        workloads = await BenchmarkRunner.get_standard_suite_workloads()

        for name, (category, fn) in workloads.items():
            for concurrency in self.concurrency_levels:
                try:
                    res = await BenchmarkRunner.run_workload(
                        name=name,
                        category=category,
                        workload_fn=fn,
                        concurrency=concurrency,
                        iterations_per_user=iterations_per_user,
                    )
                    self.results.append(res.to_dict())
                except Exception as exc:
                    logger.error(f"Error in load test {name} at concurrency {concurrency}: {exc}")
                    raise BenchmarkError(f"Load test execution failed for {name} ({concurrency} VUs): {exc}") from exc

        return self.results

    def get_summary_table_markdown(self) -> str:
        """Format test results into a GitHub-flavored Markdown comparison table."""
        if not self.results:
            return "_No load test results available._"

        lines = [
            "| Workload | Category | Concurrency (VUs) | Throughput (RPS) | P50 (ms) | P95 (ms) | P99 (ms) | Target P95 (ms) | Status |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for r in self.results:
            status_badge = "✅ PASS" if r["passed"] else "❌ FAIL"
            lines.append(
                f"| **{r['name']}** | `{r['category']}` | {r['concurrency']} | {r['throughput_rps']} | "
                f"{r['p50_ms']} | {r['p95_ms']} | {r['p99_ms']} | {r['target_p95_ms']} | {status_badge} |"
            )
        return "\n".join(lines)
