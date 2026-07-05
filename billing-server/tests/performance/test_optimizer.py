"""
test_optimizer.py — Tests for Phase 3.6 database query optimization audit and rules.
"""
import pytest
from app.performance.optimizer import auditor, RepositoryOptimizationAuditor
from app.performance.exceptions import OptimizationError


def test_repository_optimization_verification():
    assert auditor.verify_all() is True
    report = auditor.get_optimization_report()
    assert len(report) >= 8
    for item in report:
        assert item["status"] == "OPTIMIZED"
        assert item["n_plus_one_prevented"] is True


def test_optimization_failure_detection():
    test_auditor = RepositoryOptimizationAuditor()
    test_auditor._optimizations.append({
        "repository": "FakeRepository",
        "method": "bad_query",
        "status": "N+1 DETECTED",
    })

    with pytest.raises(OptimizationError, match="Repository optimization check failed"):
        test_auditor.verify_all()
