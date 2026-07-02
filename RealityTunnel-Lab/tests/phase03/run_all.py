#!/usr/bin/env python3
"""
run_all.py — Phase 0.3 test runner

Runs all automatable tests in sequence and writes a summary to results/run.log.

Usage:
    python run_all.py                    # run all tests
    python run_all.py --skip-restart     # skip test_08 (docker down/up)
    python run_all.py --skip-webhook     # skip live webhook test (test_10)
    python run_all.py --only 7 8 9      # run only specific test numbers

Tests 1–6 run the full server-side assertions.
The active-session (tunnel) measurements require a connected VPN client:
see the CLIENT REQUIRED sections printed by each test.

Set SKIP_WEBHOOK_LIVE=1 to skip only the container-restart portion of test_10.
"""

import argparse
import importlib
import os
import sys
import time
from pathlib import Path

# Add phase03 dir to path so common.py is importable
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from common import RESULTS_DIR, fail, note, ok, row, section

ALL_TESTS = [
    (1, "test_01_disable_user"),
    (2, "test_02_enable_user"),
    (3, "test_03_uuid_change"),
    (4, "test_04_expiry"),
    (5, "test_05_quota"),
    (6, "test_06_revoke_sub"),
    (7, "test_07_core_restart"),
    (8, "test_08_persistence"),
    (9, "test_09_admin_token"),
    (10, "test_10_webhooks"),
]

SESSION_TESTS = {1, 2, 3, 4, 5, 6}  # require client for tunnel measurements
RESTART_TESTS = {8}  # require docker down/up


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--skip-restart",
        action="store_true",
        help="Skip test_08 (docker compose down/up)",
    )
    p.add_argument(
        "--skip-webhook",
        action="store_true",
        help="Set SKIP_WEBHOOK_LIVE=1 for test_10",
    )
    p.add_argument(
        "--only",
        nargs="+",
        type=int,
        metavar="N",
        help="Run only the listed test numbers",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if args.skip_webhook:
        os.environ["SKIP_WEBHOOK_LIVE"] = "1"

    tests_to_run = ALL_TESTS
    if args.only:
        tests_to_run = [(n, m) for n, m in ALL_TESTS if n in args.only]
    if args.skip_restart:
        tests_to_run = [(n, m) for n, m in tests_to_run if n not in RESTART_TESTS]

    section("PHASE 0.3 — Marzban Runtime Validation")
    note(f"Running {len(tests_to_run)} test(s)")
    if any(n in SESSION_TESTS for n, _ in tests_to_run):
        note("Tests 1–6 include CLIENT REQUIRED sections for tunnel measurements.")
        note("All server-side assertions run automatically.")

    results: list[tuple[int, str, bool, float]] = []

    for number, module_name in tests_to_run:
        section(f"TEST {number:02d} — {module_name}")
        try:
            mod = importlib.import_module(module_name)
        except ImportError as e:
            fail(f"Could not import {module_name}: {e}")
            results.append((number, module_name, False, 0.0))
            continue

        t0 = time.time()
        try:
            passed = mod.run()
        except Exception as e:
            fail(f"Test raised exception: {e}")
            import traceback

            traceback.print_exc()
            passed = False
        elapsed = time.time() - t0
        results.append((number, module_name, passed, elapsed))

    # ── Summary ────────────────────────────────────────────────────────────

    section("FINAL SUMMARY")
    total_pass = sum(1 for _, _, p, _ in results if p)
    total_fail = sum(1 for _, _, p, _ in results if not p)

    for number, name, passed, elapsed in results:
        flag = f"\033[92m PASS\033[0m" if passed else f"\033[91m FAIL\033[0m"
        print(f"  [{flag} ]  Test {number:02d}  {name}  ({elapsed:.1f}s)")

    print()
    if total_fail == 0:
        ok(f"All {total_pass} tests passed")
    else:
        fail(f"{total_fail} failed, {total_pass} passed")

    # Write summary to log
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(RESULTS_DIR / "run.log", "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\n{ts}  run_all.py summary\n")
        for number, name, passed, elapsed in results:
            f.write(
                f"  {'PASS' if passed else 'FAIL'}  {number:02d} {name} ({elapsed:.1f}s)\n"
            )

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
