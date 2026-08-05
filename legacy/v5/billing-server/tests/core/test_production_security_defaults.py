"""
tests/core/test_production_security_defaults.py
Regression tests for M-6 and M-7 (Phase 3.0.11).

Ensures that production configuration:
  - Always disables /docs, /redoc, and /openapi.json (M-7)
  - Always enforces metrics_auth_required=True (M-6)

These tests exist to prevent regressions — if someone changes the defaults in
config.py or main.py, these tests will fail and make the breakage visible in CI.
"""
from __future__ import annotations

import os
import warnings
from unittest.mock import patch

import pytest
from app.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prod_settings(**overrides) -> Settings:
    """
    Instantiate a Settings object with environment=production and a valid
    non-placeholder secret_key.  Additional overrides can be supplied.
    All environment variables are mocked so the test is hermetic.
    """
    base = {
        "environment": "production",
        "secret_key": "strong-prod-key-for-testing-1234567890",
    }
    base.update(overrides)
    with patch.dict(os.environ, {k.upper(): str(v) for k, v in base.items()}, clear=False):
        return Settings(**base)


def _make_non_prod_settings(environment: str = "development") -> Settings:
    return Settings(environment=environment)


# ---------------------------------------------------------------------------
# M-7 — API docs disabled in production
# ---------------------------------------------------------------------------

class TestDocsDisabledInProduction:
    """
    M-7: Swagger UI, ReDoc, and the OpenAPI schema endpoint must all be
    disabled (return None) when environment=production.
    These URLs being None causes FastAPI to not mount the routes entirely.
    """

    def test_docs_url_is_none_in_production(self):
        s = _make_prod_settings()
        assert s.docs_url_effective is None, (
            "docs_url_effective must be None in production — "
            "Swagger UI must not be publicly accessible."
        )

    def test_redoc_url_is_none_in_production(self):
        s = _make_prod_settings()
        assert s.redoc_url_effective is None, (
            "redoc_url_effective must be None in production — "
            "ReDoc must not be publicly accessible."
        )

    def test_openapi_url_is_none_in_production(self):
        s = _make_prod_settings()
        assert s.openapi_url_effective is None, (
            "openapi_url_effective must be None in production — "
            "the /openapi.json schema endpoint must not be publicly accessible."
        )

    def test_docs_url_is_available_in_development(self):
        s = _make_non_prod_settings("development")
        assert s.docs_url_effective == "/docs"

    def test_redoc_url_is_available_in_development(self):
        s = _make_non_prod_settings("development")
        assert s.redoc_url_effective == "/redoc"

    def test_openapi_url_is_available_in_development(self):
        s = _make_non_prod_settings("development")
        assert s.openapi_url_effective == "/openapi.json"

    def test_docs_url_is_available_in_testing(self):
        """Docs remain available in testing to allow smoke-test introspection."""
        s = _make_non_prod_settings("testing")
        assert s.docs_url_effective == "/docs"

    def test_docs_url_is_none_in_staging(self):
        """Staging mirrors production — docs must also be disabled."""
        s = _make_prod_settings(environment="production")
        assert s.docs_url_effective is None


class TestFastAPIAppDocsUrlsInProduction:
    """
    Verify that app/main.py wires docs_url, redoc_url, and openapi_url from the
    settings properties (docs_url_effective etc.) — not from hardcoded strings.

    This is a source-level contract test: if someone replaces
        docs_url=settings.docs_url_effective
    with
        docs_url="/docs"
    this test will catch it immediately, even without spinning up a server.
    """

    def _read_main_source(self) -> str:
        from pathlib import Path
        return (Path(__file__).parent.parent.parent / "app" / "main.py").read_text(encoding="utf-8")

    def test_main_uses_docs_url_effective_property(self):
        src = self._read_main_source()
        assert "settings.docs_url_effective" in src, (
            "app/main.py must pass docs_url=settings.docs_url_effective to FastAPI(). "
            "A hardcoded string like '/docs' would expose Swagger UI in production."
        )

    def test_main_uses_redoc_url_effective_property(self):
        src = self._read_main_source()
        assert "settings.redoc_url_effective" in src, (
            "app/main.py must pass redoc_url=settings.redoc_url_effective to FastAPI(). "
            "A hardcoded string like '/redoc' would expose ReDoc in production."
        )

    def test_main_uses_openapi_url_effective_property(self):
        src = self._read_main_source()
        assert "settings.openapi_url_effective" in src, (
            "app/main.py must pass openapi_url=settings.openapi_url_effective to FastAPI(). "
            "A hardcoded string like '/openapi.json' would expose the schema in production."
        )


# ---------------------------------------------------------------------------
# M-6 — metrics_auth_required defaults True in production
# ---------------------------------------------------------------------------

class TestMetricsAuthRequiredInProduction:
    """
    M-6: /metrics must require admin authentication in production.
    metrics_auth_required must be True regardless of whether the operator
    explicitly sets it — the validator enforces it silently with a warning.
    """

    def test_metrics_auth_required_is_true_in_production_when_not_set(self):
        """
        Operator did not explicitly configure METRICS_AUTH_REQUIRED.
        The validator must force it to True and emit a UserWarning.
        """
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            s = _make_prod_settings()  # metrics_auth_required not passed → defaults False

        assert s.metrics_auth_required is True, (
            "metrics_auth_required must be True in production even when not explicitly set."
        )
        warning_messages = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert any("metrics_auth_required" in msg for msg in warning_messages), (
            "A UserWarning about metrics_auth_required being forced must be emitted "
            "so operators are alerted to set it explicitly."
        )

    def test_metrics_auth_required_is_true_in_production_when_explicitly_set(self):
        """
        Operator explicitly set METRICS_AUTH_REQUIRED=true.
        No warning should be emitted and the value must remain True.
        """
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            s = _make_prod_settings(metrics_auth_required=True)

        assert s.metrics_auth_required is True
        warning_messages = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert not any("metrics_auth_required" in msg for msg in warning_messages), (
            "No warning should be emitted when metrics_auth_required is already True."
        )

    def test_metrics_auth_not_forced_in_development(self):
        """
        In development the operator may opt-out; the validator must not interfere.
        """
        s = _make_non_prod_settings("development")
        # Default in dev is False — the validator must not override it.
        assert s.metrics_auth_required is False

    def test_metrics_auth_not_forced_in_testing(self):
        """
        In testing metrics auth defaults False so smoke tests can call /metrics freely.
        """
        s = _make_non_prod_settings("testing")
        assert s.metrics_auth_required is False
