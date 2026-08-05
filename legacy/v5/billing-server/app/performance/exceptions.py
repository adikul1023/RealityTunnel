"""
exceptions.py — Domain exception hierarchy for Phase 3.6 Performance & Scalability.
"""


class PerformanceError(Exception):
    """Base exception for all performance, caching, pooling, and benchmarking failures."""
    pass


class CacheError(PerformanceError):
    """Raised when caching operations fail or security policies are violated."""
    pass


class PoolingError(PerformanceError):
    """Raised when connection pooling configuration or inspection fails."""
    pass


class ProfilingError(PerformanceError):
    """Raised when profiling or resource metric collection encounters an error."""
    pass


class BenchmarkError(PerformanceError):
    """Raised when benchmark execution fails or targets cannot be evaluated."""
    pass


class OptimizationError(PerformanceError):
    """Raised during repository query optimization audit failures."""
    pass
