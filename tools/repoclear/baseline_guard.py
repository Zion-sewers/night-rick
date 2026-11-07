#!/usr/bin/env python3
"""Guard: a baseline raise must land as its own reviewed change.

CI runs this on pull requests (see .github/workflows/ship-gate.yml): when
state/repoclear-baseline.json is MODIFIED (not newly added) in the PR diff
and any other file changed alongside it, the raise is a drive-by line in a
feature PR and the guard exits 1. A baseline that is newly added (the
domain's first landing) or changed alone passes: that is the reviewed
decision the ratchet asks for. The guard reads only the git diff; it never
writes anything. It cannot see a hand-edit that lands alone (that is what
review is for), and it says so: the mechanism closes the drive-by path,
not the reviewed path.

Usage:
  python tools/repoclear/baseline_guard.py --base <sha> --head <sha> [--project .]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASELINE = "state/repoclear-baseline.json"


def guard(project: Path, base: str, head: str) -> int:
    """Exit 0 when the baseline change (if any) is its own change."""
    proc = subprocess.run(
        ["git", "-C", str(project), "diff", "--name-only",
         "--diff-filter=M", f"{base}...{head}"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        print(f"baseline guard: FAIL: cannot read the diff {base}...{head}: "
              f"{proc.stderr.strip()}", file=sys.stderr)
        return 2
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    if BASELINE not in changed:
        return 0
    others = [p for p in changed if p != BASELINE]
    if not others:
        return 0
    print("baseline guard: FAIL: state/repoclear-baseline.json is modified "
          f"alongside {len(others)} other file(s) ({', '.join(others[:5])}"
          f"{', ...' if len(others) > 5 else ''}); a baseline increase "
          "lands as its own reviewed change, never as a line in a feature PR",
          file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".")
    ap.add_argument("--base", required=True, help="PR base commit sha")
    ap.add_argument("--head", required=True, help="PR head commit sha")
    a = ap.parse_args()
    return guard(Path(a.project).resolve(), a.base, a.head)


if __name__ == "__main__":
    sys.exit(main())
