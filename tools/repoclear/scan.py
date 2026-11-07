#!/usr/bin/env python3
"""Repo Clear: the enforced half of the repo-clear standard (night-rick#35).

The epic's complaint was that the standard was prose: "A prose standard rots;
work-docs/research/README.md declares a lane the actual files ignore. So this
ships as a checker with a gate domain."

This tool is that checker, for this repository. It measures four things:

  duplicates         byte-identical documents and skill copies/forks. The
                     detection is owned by tools/audit/pile.py, which already
                     does it well and already has its own selftest and mutation
                     spec; this tool reads pile's manifest rather than
                     re-implementing the detection. One owner per detection.
  empty_dirs         directories holding no files. git never tracks these, so
                     the detector walks the filesystem, not git ls-files.
  artifacts          build artifacts tracked in git (__pycache__, node_modules,
                     .venv, target/, dist/, *.pyc, ...). Zero on main today;
                     the detector exists so a first one fails loudly.
  stale_destinations research prompts naming an output destination whose
                     directory does not exist. The 2026-07-27 prompts named
                     ~/docs/research/, which does not exist; the seven reports
                     landed in work-docs/ root instead. The check validates the
                     destination DIRECTORY, not the file to be created: a
                     prompt may name a file that does not exist yet, but the
                     directory it lands in must.

Subcommands:

  scan      human-readable report; exit 0 always (report-only).
  check     the gate: exit 1 when any count exceeds the committed baseline
            (state/repoclear-baseline.json), exit 2 when the baseline is
            missing (a missing baseline is not a pass: a gate that passes
            because nobody configured the check is the exact defect this
            repo's gate exists to catch). The baseline is a ratchet, not a
            cleanup demand: it records the measured counts on main and fails
            only on growth. Collapsing the existing duplicate/fork backlog is
            follow-up work (#92 / PR #444 and a dedup unit), not this unit.
  selftest  prove each detector fires on a planted synthetic git repo, and
            that the ratchet fires on growth and passes on no growth.

Read-only by design: scan and check never write, move, or delete anything.
--update-baseline is the one writer, and it writes only the baseline file.

Usage:
  python tools/repoclear/scan.py scan [--project .] [--json]
  python tools/repoclear/scan.py check [--project .] [--baseline PATH]
  python tools/repoclear/scan.py check --update-baseline [--project .]
  python tools/repoclear/scan.py selftest
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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PILE = ROOT / "tools" / "audit" / "pile.py"
PROMPTS_DIR = Path("work-docs") / "research" / "prompts"

SCHEMA = "repoclear-baseline.v1"

# Directories never descended into by the empty-dir walk. .claude/worktrees is
# excluded by path, not by name: sibling agent worktrees are other sessions'
# in-progress trees (one carried live conflict markers mid-merge and failed
# this tree's gate for work that was never this tree's, the same reason
# compileall excludes them).
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules",
    "__pycache__", "target", "dist", "build",
}
WORKTREES_PREFIX = Path(".claude") / "worktrees"

ARTIFACT_SEGMENTS = {
    "__pycache__", "node_modules", ".venv", "venv", "target", "dist", "build",
}
ARTIFACT_SUFFIXES = (".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe")
ARTIFACT_BASENAMES = {".DS_Store", "Thumbs.db"}

# A prompt names its output destination in one of these two shapes:
#   Output lands in ~/docs/research/.
#   Land as ~/docs/research/2026-07-rust-vs-python.md.
DEST_RE = re.compile(r"(?:Output lands in|Land as)\s+`?([^`\s]+)`?")

COUNT_KEYS = (
    "duplicate_doc_groups",
    "duplicate_doc_copies",
    "identical_skills",
    "forked_skills",
    "empty_dirs",
    "artifacts",
    "stale_destinations",
)


def _is_artifact(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p in ARTIFACT_SEGMENTS for p in parts):
        return True
    if any(p.endswith(".egg-info") for p in parts):
        return True
    if Path(rel).name in ARTIFACT_BASENAMES:
        return True
    return rel.endswith(ARTIFACT_SUFFIXES)


def _git_files(project: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(project), "ls-files"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files failed in {project}: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line]


def duplicate_counts(project: Path) -> dict[str, int]:
    """Count duplicate groups from pile.py's manifest. pile owns detection."""
    with tempfile.TemporaryDirectory() as td:
        manifest = Path(td) / "pile.jsonl"
        proc = subprocess.run(
            [sys.executable, str(PILE), "scan", "--project", str(project),
             "--out", str(manifest)],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pile.py scan failed: {proc.stderr.strip()}")
        rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    docs = [r for r in rows if r.get("kind") == "duplicate-doc"]
    ident = [r for r in rows if r.get("kind") == "identical-skill"]
    forks = [r for r in rows if r.get("kind") == "forked-skill"]
    return {
        "duplicate_doc_groups": len(docs),
        "duplicate_doc_copies": sum(r.get("copies", 0) - 1 for r in docs),
        "identical_skills": len(ident),
        "forked_skills": len(forks),
    }


def find_empty_dirs(project: Path) -> list[str]:
    """Topmost directories holding no files, filesystem walk (not git).

    git never tracks an empty directory, so git ls-files cannot see them at
    all. A directory whose only children are empty directories is not
    reported itself; its topmost empty descendant is, so a chain counts once.
    The walk is top-down so SKIP_DIRS pruning actually prevents descent
    (pruning dirs in a bottom-up walk descends anyway and reported .git
    internals until this was fixed).
    """
    records: dict[Path, tuple[list[Path], bool]] = {}
    for root, dirs, files in os.walk(project, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = Path(root).relative_to(project)
        if rel.parts[:2] == WORKTREES_PREFIX.parts:
            # A sibling session's worktree: treat as content, never as empty,
            # and do not descend into it.
            records[rel] = ([], True)
            dirs[:] = []
            continue
        records[rel] = ([rel / d for d in dirs], bool(files))
    empty: dict[Path, bool] = {}
    for rel in sorted(records, key=lambda p: len(p.parts), reverse=True):
        subdirs, has_files = records[rel]
        empty[rel] = (not has_files) and all(empty.get(s, True) for s in subdirs)
    out = []
    for rel in sorted(empty):
        if rel == Path(".") or not empty[rel]:
            continue
        parent = rel.parent
        if parent != Path(".") and empty.get(parent, False):
            continue
        out.append(str(rel))
    return out


def find_artifacts(project: Path) -> list[str]:
    """Tracked files matching build-artifact patterns."""
    return sorted(p for p in _git_files(project) if _is_artifact(p))


def _destination_dir(project: Path, raw: str) -> Path | None:
    """The directory a named output destination must land in, or None.

    A trailing slash names the directory itself; otherwise the parent
    directory. A path carrying a <placeholder> in its directory part cannot
    be resolved and is skipped, not failed: it names a template, not a place.
    """
    if raw.startswith("~"):
        target = Path(os.path.expanduser(raw))
    elif os.path.isabs(raw):
        target = Path(raw)
    else:
        target = project / raw
    checked = target if raw.endswith("/") else target.parent
    if "<" in str(checked):
        return None
    return checked


def find_stale_destinations(project: Path) -> list[dict]:
    """Prompt references whose destination directory does not exist."""
    stale: list[dict] = []
    prompts = project / PROMPTS_DIR
    if not prompts.is_dir():
        return stale
    for path in sorted(prompts.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = DEST_RE.search(line)
            if not match:
                continue
            # The destination often ends a sentence ("...research/."), and
            # Path() silently collapses a trailing "/." one level up, which
            # made a missing dir look present. Strip sentence punctuation first.
            destination = match.group(1).rstrip(".,;:")
            checked = _destination_dir(project, destination)
            if checked is None:
                continue
            if not checked.is_dir():
                stale.append({
                    "file": str(path.relative_to(project)),
                    "line": lineno,
                    "destination": destination,
                    "missing_dir": str(checked),
                })
    return stale


def collect(project: Path) -> dict:
    """Run every detector; return counts plus the detail behind them."""
    dups = duplicate_counts(project)
    empty = find_empty_dirs(project)
    artifacts = find_artifacts(project)
    stale = find_stale_destinations(project)
    counts = {
        **dups,
        "empty_dirs": len(empty),
        "artifacts": len(artifacts),
        "stale_destinations": len(stale),
    }
    return {
        "counts": counts,
        "empty_dirs": empty,
        "artifacts": artifacts,
        "stale_destinations": stale,
    }


def default_baseline_path(project: Path) -> Path:
    return project / "state" / "repoclear-baseline.json"


def load_baseline(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(f"baseline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = data.get("counts", {})
    return {k: int(counts.get(k, 0)) for k in COUNT_KEYS}


def exceeded(counts: dict[str, int], baseline: dict[str, int]) -> dict[str, tuple[int, int]]:
    """Counts that grew past the baseline: {key: (actual, baseline)}."""
    return {
        k: (counts[k], baseline[k])
        for k in COUNT_KEYS
        if counts[k] > baseline[k]
    }


def _print_report(result: dict, project: Path) -> None:
    counts = result["counts"]
    print(f"repoclear report for {project}")
    for key in COUNT_KEYS:
        print(f"  {key:<20} {counts[key]}")
    for label, items in (
        ("empty dirs", result["empty_dirs"]),
        ("tracked artifacts", result["artifacts"]),
    ):
        for item in items[:20]:
            print(f"  {label}: {item}")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more {label}")
    for item in result["stale_destinations"][:20]:
        print(f"  stale destination: {item['file']}:{item['line']} "
              f"-> {item['destination']} (missing {item['missing_dir']})")
    if len(result["stale_destinations"]) > 20:
        print(f"  ... and {len(result['stale_destinations']) - 20} more")


def cmd_scan(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    result = collect(project)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result, project)
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    baseline_path = Path(a.baseline) if a.baseline else default_baseline_path(project)
    if a.update_baseline:
        result = collect(project)
        payload = {"schema": SCHEMA, "counts": result["counts"]}
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote baseline {baseline_path}: {result['counts']}")
        return 0
    try:
        baseline = load_baseline(baseline_path)
    except FileNotFoundError as exc:
        print(f"repoclear check: FAIL: {exc} (a missing baseline is not a pass)")
        return 2
    result = collect(project)
    over = exceeded(result["counts"], baseline)
    for key in COUNT_KEYS:
        actual, base = result["counts"][key], baseline[key]
        mark = "FAIL" if key in over else "ok"
        print(f"  [{mark}] {key:<20} {actual} (baseline {base})")
    if over:
        for key, (actual, base) in over.items():
            print(f"repoclear check: FAIL: {key} grew {base} -> {actual}; "
                  "collapse the growth or update the baseline deliberately")
        return 1
    print("repoclear check: PASS: no count grew past the baseline")
    return 0


def _plant_git_repo(proj: Path) -> None:
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(proj), "config", "user.name", "t"], check=True)


def _commit(proj: Path) -> None:
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-qm", "x"], check=True)


def cmd_selftest(_a: argparse.Namespace) -> int:
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        _plant_git_repo(proj)
        (proj / "docs").mkdir()
        (proj / "old").mkdir()
        (proj / "docs" / "a.md").write_text("same body\n")
        (proj / "old" / "a.md").write_text("same body\n")
        (proj / "docs" / "b.md").write_text("unique\n")
        (proj / "planted").mkdir()
        (proj / "planted" / "empty").mkdir()
        (proj / "__pycache__").mkdir()
        (proj / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
        prompts = proj / PROMPTS_DIR
        prompts.mkdir(parents=True)
        (prompts / "p1.md").write_text("Output lands in ~/docs/no-such-dir/.\n")
        (prompts / "p2.md").write_text("Output lands in work-docs/research/.\n")
        _commit(proj)

        result = collect(proj)
        counts = result["counts"]
        if counts["duplicate_doc_groups"] != 1:
            fails.append(f"duplicate_doc_groups {counts['duplicate_doc_groups']}, want 1")
        if counts["duplicate_doc_copies"] != 1:
            fails.append(f"duplicate_doc_copies {counts['duplicate_doc_copies']}, want 1")
        if counts["empty_dirs"] != 1 or result["empty_dirs"] != ["planted"]:
            fails.append(f"empty_dirs {result['empty_dirs']}, want ['planted']")
        if counts["artifacts"] != 1 or result["artifacts"] != ["__pycache__/x.pyc"]:
            fails.append(f"artifacts {result['artifacts']}, want ['__pycache__/x.pyc']")
        if counts["stale_destinations"] != 1:
            fails.append(f"stale_destinations {counts['stale_destinations']}, want 1")
        elif result["stale_destinations"][0]["file"] != str(PROMPTS_DIR / "p1.md"):
            fails.append("the prompt naming an existing dir was reported stale, "
                         "or the missing one was not")

        baseline_path = proj / "state" / "repoclear-baseline.json"
        check_args = argparse.Namespace(
            project=str(proj), baseline=str(baseline_path), update_baseline=False)
        if cmd_check(check_args) != 2:
            fails.append("check without a baseline exited non-2; a missing "
                         "baseline must fail closed, not pass")
        check_args.update_baseline = True
        if cmd_check(check_args) != 0:
            fails.append("--update-baseline did not exit 0")
        if cmd_check(argparse.Namespace(
                project=str(proj), baseline=str(baseline_path),
                update_baseline=False)) != 0:
            fails.append("check at exactly the baseline did not pass")
        grown = dict(counts)
        grown["duplicate_doc_groups"] = counts["duplicate_doc_groups"] - 1
        baseline_path.write_text(
            json.dumps({"schema": SCHEMA, "counts": grown}, indent=2) + "\n",
            encoding="utf-8")
        if cmd_check(argparse.Namespace(
                project=str(proj), baseline=str(baseline_path),
                update_baseline=False)) != 1:
            fails.append("check with a grown duplicate count did not fail")

        # The detectors must respond to the tree, not to a hardcoded answer:
        # removing the duplicate drops the count.
        (proj / "old" / "a.md").unlink()
        _commit(proj)
        if collect(proj)["counts"]["duplicate_doc_groups"] != 0:
            fails.append("removing the duplicate did not drop the count to 0")
    for f in fails:
        print(f"[FAIL] {f}")
    print("PASS repoclear selftest" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="print the repo-clear report")
    s.add_argument("--project", default=".")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scan)
    c = sub.add_parser("check", help="fail when any count grows past the baseline")
    c.add_argument("--project", default=".")
    c.add_argument("--baseline", default="")
    c.add_argument("--update-baseline", action="store_true")
    c.set_defaults(func=cmd_check)
    t = sub.add_parser("selftest", help="prove each detector fires on a planted repo")
    t.set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
