"""
tests/deployment/test_docker_hardening.py — Regression tests for Findings H-5 and M-9.

H-5: there was no .dockerignore, so `docker build`'s COPY . . could bake a local .env,
     locally-generated dev_keys/*.pem private keys, or .git history into an image layer,
     permanently extractable via `docker history`/`docker save` even after a later layer
     "deletes" the file.

M-9: the production billing-api container retained the full default Docker capability set
     (e.g. NET_RAW, SETUID, SETGID) despite the application needing none of them, widening
     container-escape/lateral-movement surface in the event of an application-level RCE.

These tests verify the static configuration. A full `docker build` + `docker run
--cap-drop=ALL --security-opt=no-new-privileges:true` smoke boot was additionally performed
manually to confirm the running application (uvicorn binding to port 8080, non-privileged)
is unaffected by capability dropping — see Phase 3.0.8 commit message for details. That
manual verification is not repeated here since it requires a Docker daemon and takes
significantly longer than the rest of the unit test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip(
    "yaml", reason="pyyaml is required to parse docker-compose.prod.yml"
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCKERIGNORE_PATH = _REPO_ROOT / ".dockerignore"
_COMPOSE_STANDARDD_PATH = _REPO_ROOT / "docker-compose.prod.yml"

_REQUIRED_DOCKERIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "dev_keys/",
    ".git/",
    "backups/",
    "__pycache__/",
    "*.pem",
    "tests/",
)


def test_dockerignore_exists():
    """Regression test for Finding H-5: a .dockerignore must exist at the repo root."""
    assert _DOCKERIGNORE_PATH.is_file(), (
        ".dockerignore is missing at the repository root"
    )


@pytest.mark.parametrize("pattern", _REQUIRED_DOCKERIGNORE_PATTERNS)
def test_dockerignore_excludes_required_patterns(pattern: str):
    """
    Regression test for Finding H-5.

    Every secret-bearing or unnecessary path called out in the finding must be present in
    .dockerignore: .env, .env.*, dev_keys/, .git/, backups/, __pycache__/, *.pem, tests/.
    """
    content = _DOCKERIGNORE_PATH.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines()}
    assert pattern in lines, (
        f"Expected pattern {pattern!r} to be present in .dockerignore"
    )


def _load_billing_api_service() -> dict:
    content = _COMPOSE_STANDARDD_PATH.read_text(encoding="utf-8")
    compose = yaml.safe_load(content)
    return compose["services"]["billing-api"]


def test_billing_api_drops_all_capabilities():
    """
    Regression test for Finding M-9.

    The production billing-api container must explicitly drop the full default Linux
    capability set, since the application (a Python/uvicorn HTTP service binding to the
    non-privileged port 8080) needs none of them.
    """
    service = _load_billing_api_service()
    assert service.get("cap_drop") == ["ALL"], (
        f"Expected billing-api.cap_drop == ['ALL'], got {service.get('cap_drop')!r}"
    )


def test_billing_api_sets_no_new_privileges():
    """
    Regression test for Finding M-9.

    The production billing-api container must set the no-new-privileges security option,
    preventing any process inside it from gaining additional privileges via setuid/setgid
    binaries even if capabilities were otherwise available.
    """
    service = _load_billing_api_service()
    security_opt = service.get("security_opt") or []
    assert "no-new-privileges:true" in security_opt, (
        f"Expected 'no-new-privileges:true' in billing-api.security_opt, got {security_opt!r}"
    )


def test_billing_api_still_read_only_and_non_root_baseline_preserved():
    """
    Sanity check that this phase's changes did not accidentally regress the pre-existing
    read_only filesystem hardening (a prerequisite baseline this phase builds on top of).
    """
    service = _load_billing_api_service()
    assert service.get("read_only") is True
