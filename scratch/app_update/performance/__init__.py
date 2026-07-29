"""
app.performance — Performance, Scalability & Load Testing package (Phase 3.6).
Orthogonal utilities for caching, connection pool tuning, profiling, and benchmarking.
"""
from app.performance.exceptions import (
    PerformanceError,
    CacheError,
    PoolingError,
    ProfilingError,
    BenchmarkError,
    OptimizationError,
)
from app.performance.cache import BaseCache, MemoryCache, RedisCache, get_cache, validate_cache_key
from app.performance.pooling import get_engine_pool_kwargs, get_pool_status
from app.performance.profiler import profiler, PerformanceProfiler
from app.performance.optimizer import auditor, RepositoryOptimizationAuditor
from app.performance.benchmarks import BenchmarkRunner, BenchmarkResult
from app.performance.load_testing import LoadTestSuite

__all__ = [
    "PerformanceError",
    "CacheError",
    "PoolingError",
    "ProfilingError",
    "BenchmarkError",
    "OptimizationError",
    "BaseCache",
    "MemoryCache",
    "RedisCache",
    "get_cache",
    "validate_cache_key",
    "get_engine_pool_kwargs",
    "get_pool_status",
    "profiler",
    "PerformanceProfiler",
    "auditor",
    "RepositoryOptimizationAuditor",
    "BenchmarkRunner",
    "BenchmarkResult",
    "LoadTestSuite",
]
