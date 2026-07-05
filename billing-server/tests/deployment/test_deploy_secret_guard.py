"""
test_deploy_secret_guard.py - Regression tests for Findings C-5 and H-1.

C-5: deployment/production/deploy.sh used invalid bash syntax
     ([ -z "$A" ] or [ -z "$B" ]) in its required-secrets pre-flight guard, which meant
     the guard NEVER actually fired regardless of whether POSTGRES_PASSWORD was set. These
     tests invoke the real deploy.sh (and deploy.ps1) as subprocesses with a controlled
     environment to prove the guard now correctly blocks deployment when POSTGRES_PASSWORD
     is missing, and does not block when it is present.

H-1: JWT_SECRET (along with MASTER_TOKEN_HASH and API_KEY) was required by
     docker-compose.prod.yml and deploy.sh/deploy.ps1 but has no corresponding field in
     app/config.py::Settings and is never read by the application; actual JWT signing uses
     Ed25519 PEM keypairs on disk. These tests confirm JWT_SECRET is no longer required by
     either deploy script's guard.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

DEPLOYMENT_DIR = (
    Path(__file__).resolve().parent.parent.parent / "deployment" / "production"
)
DEPLOY_SH = DEPLOYMENT_DIR / "deploy.sh"
DEPLOY_PS1 = DEPLOYMENT_DIR / "deploy.ps1"
COMPOSE_PROD = (
    Path(__file__).resolve().parent.parent.parent / "docker-compose.prod.yml"
)

# Guard-check subprocesses may proceed past the guard into real docker/python calls that
# are not available (or not desired) in a CI/test sandbox. A short timeout is sufficient
# to observe whether the guard blocked execution, without waiting for those later steps
# to fully succeed or fail.
GUARD_OBSERVATION_TIMEOUT_SECONDS = 10


def _bash_can_execute_scripts(bash_path: str) -> bool:
    """
    Return True only if bash can run real shell scripts and `[ ]` test syntax.

    On Windows, System32/bash.exe is a WSL launcher stub that may appear on PATH
    before a real Git/bash binary. It can fail with an RPC error when executing
    .sh files even though trivial `-c` probes sometimes succeed — so we verify
    both test-syntax and script-file execution (the C-5 guard relies on `[ -z ]`).
    """
    try:
        syntax_probe = subprocess.run(
            [bash_path, "-c", 'if [ -z "$UNSET_VAR_FOR_GUARD_TEST" ]; then echo blocked; fi'],
            capture_output=True,
            text=True,
            timeout=5,
            env={"PATH": os.environ.get("PATH", "")},
        )
        if syntax_probe.returncode != 0 or "blocked" not in syntax_probe.stdout:
            return False

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sh",
            delete=False,
            encoding="utf-8",
            newline="\n",
        ) as script_file:
            script_file.write("#!/usr/bin/env bash\n")
            script_file.write('if [ -z "$POSTGRES_PASSWORD" ]; then exit 1; fi\n')
            script_file.write('echo "guard passed"\n')
            script_path = script_file.name

        try:
            unset_probe = subprocess.run(
                [bash_path, script_path],
                capture_output=True,
                text=True,
                timeout=5,
                env={"PATH": os.environ.get("PATH", "")},
            )
            if unset_probe.returncode != 1:
                return False

            set_probe = subprocess.run(
                [bash_path, script_path],
                capture_output=True,
                text=True,
                timeout=5,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "POSTGRES_PASSWORD": "probe-value",
                },
            )
            return (
                set_probe.returncode == 0
                and "guard passed" in set_probe.stdout
            )
        finally:
            Path(script_path).unlink(missing_ok=True)
    except Exception:
        return False


def _find_working_bash() -> str | None:
    """
    Locate a real, executable bash binary.

    On Windows, `shutil.which("bash")` / PATH order can resolve to
    C:\\Windows\\System32\\bash.exe, which is a thin launcher for WSL and fails with an
    RPC error when WSL is not fully initialized in a sandboxed environment - even though
    a perfectly good Git-for-Windows bash.exe may also be on PATH. Probe every "bash" on
    PATH and return the first one that actually runs a trivial command successfully.
    """
    seen: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = (
            Path(directory) / "bash.exe"
            if os.name == "nt"
            else Path(directory) / "bash"
        )
        candidate_str = str(candidate)
        if candidate_str in seen or not candidate.is_file():
            continue
        seen.add(candidate_str)
        try:
            probe = subprocess.run(
                [candidate_str, "-c", "echo ok"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if probe.returncode == 0 and "ok" in probe.stdout and _bash_can_execute_scripts(
                candidate_str
            ):
                return candidate_str
        except Exception:
            continue
    # Fall back to whatever shutil.which finds (may still work on non-Windows CI runners).
    fallback = shutil.which("bash")
    if fallback and _bash_can_execute_scripts(fallback):
        return fallback
    return None


_WORKING_BASH = _find_working_bash()


def _run_deploy_sh(env_overrides: dict[str, str]) -> tuple[int, str]:
    """
    Run deploy.sh with a minimal, controlled environment (PATH only, plus overrides).
    Returns (exit_code, combined_stdout_stderr). If the script proceeds past the guard
    into long-running steps (docker pull, health check polling), the subprocess is
    terminated after GUARD_OBSERVATION_TIMEOUT_SECONDS and whatever output was captured
    up to that point is returned with a sentinel exit code of -1 (timed out).
    """
    env = {"PATH": os.environ.get("PATH", "")}
    env.update(env_overrides)

    try:
        result = subprocess.run(
            [_WORKING_BASH, str(DEPLOY_SH)],
            cwd=str(DEPLOYMENT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=GUARD_OBSERVATION_TIMEOUT_SECONDS,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        )
        return -1, stdout + stderr


@pytest.mark.skipif(
    _WORKING_BASH is None, reason="no working bash executable found on this system"
)
def test_deploy_sh_blocks_when_postgres_password_missing():
    """
    Regression test for Finding C-5.

    With POSTGRES_PASSWORD unset, deploy.sh must exit non-zero immediately at the guard,
    printing the ERROR message, and must NEVER reach the deployment steps that follow
    (proven by the absence of the 'Creating pre-deployment database backup' log line).
    """
    exit_code, output = _run_deploy_sh({})

    assert exit_code == 1, (
        f"Expected deploy.sh to exit 1 when POSTGRES_PASSWORD is unset, got {exit_code}.\n"
        f"Output:\n{output}"
    )
    assert "POSTGRES_PASSWORD" in output
    assert "ERROR" in output
    assert "Creating pre-deployment database backup" not in output


@pytest.mark.skipif(
    _WORKING_BASH is None, reason="no working bash executable found on this system"
)
def test_deploy_sh_does_not_require_jwt_secret():
    """
    Regression test for Finding H-1.

    JWT_SECRET is dead configuration and must no longer be required by deploy.sh's guard.
    With POSTGRES_PASSWORD set and JWT_SECRET deliberately left unset, the guard must not
    block: the script must proceed past it (observed via the first post-guard log line).
    """
    exit_code, output = _run_deploy_sh({"POSTGRES_PASSWORD": "test-password-value"})

    assert "ERROR" not in output, f"Guard unexpectedly blocked deployment:\n{output}"
    assert "Creating pre-deployment database backup" in output, (
        "Expected deploy.sh to proceed past the secret guard when POSTGRES_PASSWORD is set "
        f"(even though JWT_SECRET is unset), but it did not.\nOutput:\n{output}"
    )


def test_deploy_sh_guard_uses_valid_bash_syntax():
    """
    Regression test for Finding C-5 (root cause verification).

    Directly proves the specific broken syntax ([ ... ] or [ ... ]) that silently
    disabled the guard is no longer present anywhere in deploy.sh, and that only
    POSTGRES_PASSWORD (not the dead JWT_SECRET) is referenced in the guard.
    """
    content = DEPLOY_SH.read_text(encoding="utf-8")
    guard_line = next(
        line for line in content.splitlines() if line.strip().startswith("if [ -z")
    )

    assert " or " not in guard_line, (
        f"Broken bash 'or' syntax still present in guard: {guard_line!r}"
    )
    assert "POSTGRES_PASSWORD" in guard_line
    assert "JWT_SECRET" not in guard_line


def test_deploy_ps1_does_not_require_jwt_secret():
    """
    Regression test for Finding H-1 (PowerShell counterpart).

    deploy.ps1's guard used valid PowerShell syntax already (no C-5-equivalent bug there),
    but it still referenced the dead JWT_SECRET variable. Confirm it has been removed and
    only POSTGRES_PASSWORD remains required.
    """
    content = DEPLOY_PS1.read_text(encoding="utf-8")
    guard_line = next(
        line
        for line in content.splitlines()
        if line.strip().startswith("if (-not $env:POSTGRES_PASSWORD")
    )

    assert "JWT_SECRET" not in guard_line
    assert "POSTGRES_PASSWORD" in guard_line


def test_deploy_ps1_blocks_when_postgres_password_missing():
    """
    Regression test for Finding C-5 (PowerShell counterpart).

    With POSTGRES_PASSWORD unset, deploy.ps1 must exit non-zero immediately at the guard.
    """
    env = {k: v for k, v in os.environ.items() if k != "POSTGRES_PASSWORD"}
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DEPLOY_PS1),
        ],
        cwd=str(DEPLOYMENT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=GUARD_OBSERVATION_TIMEOUT_SECONDS,
    )

    assert result.returncode == 1, (
        f"Expected deploy.ps1 to exit 1 when POSTGRES_PASSWORD is unset, got {result.returncode}.\n"
        f"Output:\n{(result.stdout or '') + (result.stderr or '')}"
    )
    output = (result.stdout or "") + (result.stderr or "")
    assert "POSTGRES_PASSWORD" in output
    assert "ERROR" in output
    assert "Creating pre-deployment database backup" not in output


def test_docker_compose_prod_does_not_require_jwt_secret():
    """
    Regression test for Finding H-1.

    docker-compose.prod.yml must not require JWT_SECRET, MASTER_TOKEN_HASH, or API_KEY.
    """
    content = COMPOSE_PROD.read_text(encoding="utf-8")

    for dead_var in ("JWT_SECRET", "MASTER_TOKEN_HASH", "API_KEY"):
        assert f"${{{dead_var}" not in content, (
            f"docker-compose.prod.yml still references dead env var {dead_var}"
        )
    assert "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required for production}" in content
