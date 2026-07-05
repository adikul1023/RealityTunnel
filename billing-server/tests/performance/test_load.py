"""
test_load.py — Tests for Phase 3.6 load testing runner and benchmark suite execution.
"""
import pytest
from app.performance.benchmarks import BenchmarkRunner, BenchmarkResult
from app.performance.load_testing import LoadTestSuite


@pytest.mark.asyncio
async def test_benchmark_runner_single_workload():
    async def _dummy_workload():
        pass

    res = await BenchmarkRunner.run_workload(
        name="Dummy Workload",
        category="anonymous",
        workload_fn=_dummy_workload,
        concurrency=10,
        iterations_per_user=2,
    )

    assert isinstance(res, BenchmarkResult)
    assert res.total_requests == 20
    assert res.errors == 0
    assert res.passed is True
    assert "throughput_rps" in res.to_dict()


@pytest.mark.asyncio
async def test_load_test_suite_execution():
    # Use smaller concurrency for fast unit testing
    suite = LoadTestSuite(concurrency_levels=(10, 25))
    results = await suite.execute_all(iterations_per_user=1)

    assert len(results) == 8 * 2  # 8 standard workloads x 2 concurrency levels
    for r in results:
        assert r["errors"] == 0
        assert r["passed"] is True
        assert r["p95_ms"] >= 0.0

    md_table = suite.get_summary_table_markdown()
    assert "| **Authentication** |" in md_table
    assert "✅ PASS" in md_table
