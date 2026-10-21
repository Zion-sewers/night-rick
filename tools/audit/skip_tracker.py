#!/usr/bin/env python3
"""Track pytest skip counts and fail when they rise.

A skip is not a pass. L-2026-07-29-i records the incident: a generator bug
deleted content from 12 shipped files, four tests responded with pytest.skip()
instead of failing, the suite reported "89 passed, 4 skipped", and the gate
read that as PASS. The artifacts were visibly corrupt while every automated
check was green.

This tool parses pytest summary lines, stores a baseline, and fails when the
skip count rises above it. A rising skip count is the signal the gate was
missing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_FILE = "state/skip-baseline.json"

_SUMMARY_RE = re.compile(
    r"(\d+) passed"
    r"(?:,\s*(\d+) skipped)?"
    r"(?:,\s*(\d+) xfailed)?"
    r"(?:,\s*(\d+) warnings?)?"
)


def _parse_pytest_summary(output: str) -> dict[str, int] | None:
    """Extract pass/skip counts from pytest -q output."""
    for line in reversed(output.splitlines()):
        m = _SUMMARY_RE.search(line)
        if m:
            return {
                "passed": int(m.group(1)),
                "skipped": int(m.group(2) or 0),
            }
    return None


def _run_suites(project: str) -> list[dict[str, int | str]]:
    """Run each test suite and return parsed results."""
    suites = [
        {"name": "root", "cmd": [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"]},
    ]
    icp = os.path.join(project, "intent-control-plane")
    if os.path.isdir(icp) and os.path.isfile(os.path.join(icp, "pyproject.toml")):
        suites.append({
            "name": "intent-control-plane",
            "cmd": ["uv", "run", "pytest", "-q", "--tb=no"],
            "cwd": icp,
        })

    results = []
    for suite in suites:
        cwd = suite.get("cwd", project)
        try:
            r = subprocess.run(
                suite["cmd"], capture_output=True, text=True,
                timeout=300, cwd=cwd, check=False,
            )
            parsed = _parse_pytest_summary(r.stdout)
            if parsed is None:
                parsed = _parse_pytest_summary(r.stderr)
            if parsed is not None:
                parsed["name"] = suite["name"]
                results.append(parsed)
            else:
                print(f"WARNING: could not parse summary for {suite['name']}")
        except subprocess.TimeoutExpired:
            print(f"WARNING: {suite['name']} timed out")
        except FileNotFoundError as e:
            print(f"WARNING: {suite['name']} could not start ({e}); skipping suite")
    return results


def load_baseline(project: str) -> dict[str, int]:
    """Load the skip baseline: {suite_name: skip_count}."""
    path = os.path.join(project, BASELINE_FILE)
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_baseline(project: str, baseline: dict[str, int]) -> None:
    path = os.path.join(project, BASELINE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(baseline, f, indent=2, sort_keys=True)
        f.write("\n")


def check(project: str) -> tuple[int, list[str]]:
    """Compare current skip counts against the baseline."""
    baseline = load_baseline(project)
    if not baseline:
        print("no skip baseline found; run `update` first to establish one")
        return 2, []

    results = _run_suites(project)
    if not results:
        print("no test suites produced parseable output")
        return 1, ["no parseable pytest output"]

    findings: list[str] = []
    for r in results:
        name = r["name"]
        current_skips = r["skipped"]
        baseline_skips = baseline.get(name, 0)
        print(f"  {name}: {r['passed']} passed, {current_skips} skipped (baseline: {baseline_skips})")
        if current_skips > baseline_skips:
            msg = f"SKIP REGRESSION: {name} skips rose from {baseline_skips} to {current_skips} (+{current_skips - baseline_skips})"
            findings.append(msg)
            print(f"  {msg}")

    if findings:
        print(f"\n{len(findings)} skip regression(s) found")
        return 1, findings

    print("\nskip counts at or below baseline")
    return 0, findings


def update(project: str) -> int:
    """Run suites and save current skip counts as the new baseline."""
    results = _run_suites(project)
    if not results:
        print("no test suites produced parseable output")
        return 1

    baseline = {}
    for r in results:
        baseline[r["name"]] = r["skipped"]
        print(f"  {r['name']}: {r['passed']} passed, {r['skipped']} skipped")

    save_baseline(project, baseline)
    print(f"\nbaseline saved to {BASELINE_FILE}")
    return 0


def selftest() -> int:
    """Prove the tracker catches rising skip counts."""
    failures: list[str] = []

    # Test 1: _parse_pytest_summary with skips
    parsed = _parse_pytest_summary("742 passed, 31 skipped, 1 xfailed in 22.29s")
    if parsed is None or parsed["passed"] != 742 or parsed["skipped"] != 31:
        failures.append(f"parse with skips: got {parsed}")

    # Test 2: _parse_pytest_summary without skips
    parsed = _parse_pytest_summary("435 passed in 8.25s")
    if parsed is None or parsed["passed"] != 435 or parsed["skipped"] != 0:
        failures.append(f"parse without skips: got {parsed}")

    # Test 3: _parse_pytest_summary with warnings
    parsed = _parse_pytest_summary("100 passed, 2 skipped, 3 warnings in 5.0s")
    if parsed is None or parsed["passed"] != 100 or parsed["skipped"] != 2:
        failures.append(f"parse with warnings: got {parsed}")

    # Test 4: check detects a regression
    import unittest.mock as mock
    this_module = sys.modules[__name__]
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        baseline_path = os.path.join(state_dir, "skip-baseline.json")
        with open(baseline_path, "w") as f:
            json.dump({"root": 5, "intent-control-plane": 0}, f)

        fake_results = [
            {"name": "root", "passed": 740, "skipped": 8},
            {"name": "intent-control-plane", "passed": 435, "skipped": 0},
        ]
        with mock.patch.object(this_module, "_run_suites", return_value=fake_results):
            code, findings = check(tmp)
        if code != 1:
            failures.append(f"rising skips returned {code}, expected 1")
        if not any("SKIP REGRESSION" in f and "root" in f for f in findings):
            failures.append("the regression was not named in findings")

    # Test 5: check passes when skips are at baseline
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        baseline_path = os.path.join(state_dir, "skip-baseline.json")
        with open(baseline_path, "w") as f:
            json.dump({"root": 31, "intent-control-plane": 0}, f)

        fake_results = [
            {"name": "root", "passed": 742, "skipped": 31},
            {"name": "intent-control-plane", "passed": 435, "skipped": 0},
        ]
        with mock.patch.object(this_module, "_run_suites", return_value=fake_results):
            code, findings = check(tmp)
        if code != 0:
            failures.append(f"skips at baseline returned {code}, expected 0")

    # Test 6: check passes when skips decreased
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = os.path.join(tmp, "state")
        os.makedirs(state_dir)
        baseline_path = os.path.join(state_dir, "skip-baseline.json")
        with open(baseline_path, "w") as f:
            json.dump({"root": 31}, f)

        fake_results = [
            {"name": "root", "passed": 750, "skipped": 20},
        ]
        with mock.patch.object(this_module, "_run_suites", return_value=fake_results):
            code, findings = check(tmp)
        if code != 0:
            failures.append(f"decreased skips returned {code}, expected 0")

    # Test 7: no baseline returns 2
    with tempfile.TemporaryDirectory() as tmp:
        code, _ = check(tmp)
        if code != 2:
            failures.append(f"no baseline returned {code}, expected 2")

    for line in failures:
        print(f"FAIL {line}")
    if not failures:
        print(f"PASS skip_tracker selftest ({7} checks)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("check", "update", "selftest"), default="check", nargs="?")
    parser.add_argument("--project", default=os.getcwd())
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()
    if args.command == "update":
        return update(args.project)
    code, _ = check(args.project)
    return code


if __name__ == "__main__":
    sys.exit(main())
