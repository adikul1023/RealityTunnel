"""
test_admin_password.py — Regression tests for Audit Finding H1.

H1: The dummy Argon2id hash used to defend against admin-username-enumeration timing attacks
(`DUMMY_ADMIN_PASSWORD_HASH` in app/security/admin_password.py) was previously a hand-crafted,
structurally invalid PHC string. Because the underlying Argon2 implementation could not decode it,
`verify()` failed in under a millisecond instead of running the full ~68ms memory-hard KDF that a
real hash requires -- creating a large, network-measurable timing gap between "admin exists" and
"admin does not exist" login attempts.

These tests directly target the root cause (a malformed dummy hash short-circuiting the KDF), not
just the symptom (timing difference), by asserting:

1. The dummy hash always fails with `VerifyMismatchError` (a legitimate digest mismatch after running
   the full KDF), never `VerificationError`/`InvalidHashError` (a decode failure that skips the KDF).
2. The measured wall-clock cost of verifying against the dummy hash is statistically indistinguishable
   from the cost of verifying against a real hash generated from an actual admin password.
"""

from __future__ import annotations

import statistics
import time

import pytest
from app.security.admin_password import (
    _ADMIN_ARGON2_PARAMS,
    DUMMY_ADMIN_PASSWORD_HASH,
    AdminPasswordService,
)
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


def _median_verify_duration(
    service: AdminPasswordService, candidate: str, target_hash: str, samples: int
) -> float:
    """
    Run `verify_password` `samples` times against `target_hash` and return the median wall-clock
    duration in seconds. Median (rather than mean) is used to reduce sensitivity to single-sample
    OS scheduling noise/outliers, which is important for CI stability.
    """
    durations: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        service.verify_password(candidate, target_hash)
        durations.append(time.perf_counter() - start)
    return statistics.median(durations)


class TestDummyHashStructuralValidity:
    """
    Root-cause regression test: the dummy hash must be a well-formed Argon2id digest that always
    runs the complete KDF, never one that fails to parse/decode.
    """

    def test_dummy_hash_has_valid_argon2id_prefix(self):
        """The dummy hash must be a syntactically valid Argon2id PHC-format string."""
        assert DUMMY_ADMIN_PASSWORD_HASH.startswith("$argon2id$")

    def test_dummy_hash_uses_the_same_parameters_as_real_hashing(self):
        """
        The dummy hash must encode the exact same time_cost/memory_cost/parallelism as the
        parameters used for real admin password hashing, so verification cost is identical.
        """
        expected_fragment = (
            f"$v=19$m={_ADMIN_ARGON2_PARAMS['memory_cost']},"
            f"t={_ADMIN_ARGON2_PARAMS['time_cost']},"
            f"p={_ADMIN_ARGON2_PARAMS['parallelism']}$"
        )
        assert expected_fragment in DUMMY_ADMIN_PASSWORD_HASH

    @pytest.mark.parametrize(
        "candidate", ["", "wrong-password", "correct horse battery staple", "a" * 200]
    )
    def test_verify_against_dummy_hash_never_raises_decode_errors(self, candidate: str):
        """
        Directly targets the root cause of H1: calling the underlying hasher's `verify()` against
        the dummy hash must always run the full KDF and fail with a content mismatch
        (`VerifyMismatchError`), and must never fail structurally with `VerificationError` or
        `InvalidHashError` (which would indicate the hash is malformed/undecodable and the KDF was
        skipped entirely -- the exact defect being regression-tested here).
        """
        service = AdminPasswordService()

        # Reach into the real Argon2 hasher directly (bypassing verify_password's broad except
        # Exception handler) so a structural decode failure cannot be silently swallowed by this test.
        with pytest.raises(VerifyMismatchError):
            service._hasher.verify(DUMMY_ADMIN_PASSWORD_HASH, candidate)

        # verify_password() (the public API) must still correctly report False for every candidate.
        assert service.verify_password(candidate, DUMMY_ADMIN_PASSWORD_HASH) is False

    def test_execute_timing_defense_does_not_raise(self):
        """execute_timing_defense() must remain a safe no-throw call regardless of input."""
        service = AdminPasswordService()
        service.execute_timing_defense("any-candidate-password")
        service.execute_timing_defense("")


class TestDummyHashTimingParity:
    """
    Statistical regression test: verifying against the dummy hash must cost approximately the same
    wall-clock time as verifying against a real hash, so an external timing observer cannot
    distinguish "admin exists" from "admin does not exist" via response latency.
    """

    def test_dummy_and_real_hash_verification_cost_is_statistically_indistinguishable(
        self,
    ):
        service = AdminPasswordService()
        real_hash = service.hash_password("a-realistic-admin-password-1234")

        samples = 7

        # Warm up interpreter/JIT-adjacent caches and OS scheduling before the timed measurement.
        service.verify_password("warmup", DUMMY_ADMIN_PASSWORD_HASH)
        service.verify_password("warmup", real_hash)

        dummy_median = _median_verify_duration(
            service, "wrong-password", DUMMY_ADMIN_PASSWORD_HASH, samples
        )
        real_median = _median_verify_duration(
            service, "wrong-password", real_hash, samples
        )

        # Both must be dominated by the memory-hard KDF (tens of milliseconds), not a near-instant
        # decode failure. This directly catches a regression back to a malformed/undecodable hash.
        assert dummy_median > 0.005, (
            f"Dummy hash verification took {dummy_median * 1000:.3f}ms -- suspiciously fast, "
            "suggesting the dummy hash is failing to decode instead of running the full KDF."
        )

        # The two costs must be within a generous tolerance of each other. This is not asserting
        # both are merely "fast" -- it asserts they are statistically indistinguishable from one
        # another, which is the actual security property being defended.
        tolerance = 0.30
        ratio = dummy_median / real_median
        assert (1 - tolerance) <= ratio <= (1 + tolerance), (
            f"Timing side-channel regression: dummy-hash verification ({dummy_median * 1000:.3f}ms) "
            f"and real-hash verification ({real_median * 1000:.3f}ms) differ by more than "
            f"{tolerance * 100:.0f}% (ratio={ratio:.3f}). This would allow network-based admin "
            "username enumeration via timing analysis."
        )
