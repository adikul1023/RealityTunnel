"""
test_profiler.py — Tests for Phase 3.6 automatic latency profiling and resource monitoring.
"""
import pytest
from app.performance.profiler import PerformanceProfiler, profiler


def test_percentile_calculation_accuracy():
    p = PerformanceProfiler()
    # Provide 100 samples from 1ms to 100ms (0.001 to 0.100s)
    samples = [i / 1000.0 for i in range(1, 101)]
    pcts = p.calculate_percentiles(samples)

    assert pcts["count"] == 100
    assert pcts["p50"] == 50.0
    assert pcts["p90"] == 90.0
    assert pcts["p95"] == 95.0
    assert pcts["p99"] == 99.0
    assert pcts["avg"] > 0.0


def test_profiler_recording_and_category_retrieval():
    p = PerformanceProfiler()
    p.record_latency("query", 0.010)
    p.record_latency("query", 0.015)
    p.record_latency("query", 0.020)
    p.record_latency("endpoint", 0.050)

    q_pcts = p.get_category_percentiles("query")
    assert q_pcts["count"] == 3
    assert q_pcts["p50"] == 15.0

    all_pcts = p.get_all_percentiles()
    assert "query" in all_pcts
    assert "endpoint" in all_pcts


def test_resource_usage_collection():
    res = profiler.get_resource_usage()
    assert "cpu_usage_percent" in res
    assert "memory_usage_bytes" in res
    assert "active_asyncio_tasks" in res
    assert "db_pool_usage" in res
    assert res["memory_usage_bytes"] > 0
