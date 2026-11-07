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
                     A skipped child (__pycache__/, node_modules/, build/,
                     ...) counts as content, not absence: a directory whose
                     only child is a skipped directory holding real files is
                     not empty.
  artifacts          build artifacts tracked in git (__pycache__, node_modules,
                     .venv, target/, dist/, *.pyc, ...). Zero on main today;
                     the detector exists so a first one fails loudly.
                     Matching is case-insensitive (X.PYC is an artifact),
                     and git ls-files runs -z so non-ASCII names survive
                     quoting.
  stale_destinations research prompts naming an output destination whose
                     directory does not exist. The 2026-07-27 prompts named
                     ~/docs/research/, which does not exist; the seven reports
                     landed in work-docs/ root instead. The check validates the
                     destination DIRECTORY, not the file to be created: a
                     last component with a file extension names a file, so its
                     parent is checked; anything else names the directory
                     itself. Every destination on a line is examined and the
                     lead-ins match case-insensitively. It validates directory
                     existence ONLY: it does not prove reports land there (the
                     seven reports are still in work-docs/ root; relocating
                     them is #447). A destination under ~ is unresolvable
                     inside the repo and counts as stale, and a prompt with no
                     machine-readable destination ("Output lands in <dir>" or
                     "Land as <path>") counts as stale too: a prompt the check
                     cannot parse is a prompt the check cannot verify.

Subcommands:

  scan      human-readable report; exit 0 always (report-only).
  check     the gate: exit 1 when any count exceeds the committed baseline
            (state/repoclear-baseline.json), exit 2 when the baseline is
            missing or malformed (a missing baseline is not a pass: a gate
            that passes because nobody configured the check is the exact
            defect this repo's gate exists to catch). The baseline is a
            ratchet, not a cleanup demand: it records the measured counts on
            main and fails only on growth. Collapsing the existing
            duplicate/fork backlog is follow-up work (#446), not this unit.
            A baseline increase is a reviewed decision, never a drive-by line
            in a feature PR: check --update-baseline refuses under CI, and
            the baseline file carries measured_on, base_commit,
            recheck_after, and follow_up provenance, validated on load.
  selftest  prove each detector fires on a planted synthetic git repo, and
            that the ratchet fires on growth and passes on no growth.

Read-only by design: scan and check never write, move, or delete anything.
--update-baseline is the one writer, and it writes only the baseline file,
and only from a developer machine, never under CI.

Detector scopes, stated so they can be argued with: duplicates and tracked
artifacts are computed from git ls-files (tracked files only), while empty
dirs are computed from a filesystem walk (tracked, untracked, and ignored
alike, minus SKIP_DIRS). A clean CI checkout and a dirty developer tree
therefore measure the same tracked counts but can differ on empty dirs.
Timeouts are set from the measured runtime (about 2s total on main): the
contract allows 60s, pile.py gets 45s, git gets 30s, so a hang surfaces as a
domain failure with evidence, not a silent gate timeout.
The pile.py manifest the gate counts is re-derived on every run (pile.py is
deterministic); to reproduce a red gate, re-run pile.py scan, whose output
is the same manifest.
The scanner is night-rick only today: porting it to another repo means
copying the tool, the contract domain, and a measured baseline, not just
passing --project (the other repos have no pile.py, no repoclear domain,
and no baseline).

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
DEST_RE = re.compile(r"(?:Output lands in|Land as)\s+`?([^`\s]+)`?",
                     re.IGNORECASE)

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
    # Case-insensitive: X.PYC is a build artifact the same as x.pyc.
    # Segment test is deliberately broad by design: ANY directory named
    # build/ (or dist/, target/, ...) is treated as an artifact container,
    # so docs/build/guide.md counts as an artifact. No tracked file in this
    # repo trips that today; narrowing it is a follow-up, not a silent fix.
    low = rel.lower()
    parts = Path(low).parts
    if any(p in ARTIFACT_SEGMENTS for p in parts):
        return True
    if any(p.endswith(".egg-info") for p in parts):
        return True
    if Path(low).name in {b.lower() for b in ARTIFACT_BASENAMES}:
        return True
    return low.endswith(ARTIFACT_SUFFIXES)


def _git_files(project: Path) -> list[str]:
    # -z: NUL-separated, unquoted. Plain ls-files quotes non-ASCII paths
    # under core.quotepath, so a tracked __pycache__/café.pyc arrived as
    # the literal string '"__pycache__/caf\303\251.pyc"' and never matched.
    proc = subprocess.run(
        ["git", "-C", str(project), "ls-files", "-z"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files failed in {project}: {proc.stderr.strip()}")
    return [entry for entry in proc.stdout.split("\0") if entry]


PILE_SCHEMA = "pile.v1"
PILE_KINDS = ("duplicate-doc", "identical-skill", "forked-skill")


def duplicate_counts(project: Path) -> dict[str, int]:
    """Count duplicate groups from pile.py's manifest. pile owns detection.

    Fail-closed on the seam: a manifest row without schema pile.v1, with an
    unknown kind, or with a duplicate-doc copies count below 2 (a group has
    at least two copies by construction) raises instead of counting as zero.
    A zero row set is legitimate (a clean repo emits no rows) and is covered
    the other way: the selftest plants one group of each kind and asserts the
    counts, so a pile.py that silently stopped seeing groups goes red there.
    Requiring every kind to be present would fail every clean repo, so kinds
    are validated when present, not required.
    """
    with tempfile.TemporaryDirectory() as td:
        manifest = Path(td) / "pile.jsonl"
        try:
            proc = subprocess.run(
                [sys.executable, str(PILE), "scan", "--project", str(project),
                 "--out", str(manifest)],
                capture_output=True, text=True, timeout=45,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"pile.py scan timed out after 45s: {exc}")
        if proc.returncode != 0:
            raise RuntimeError(f"pile.py scan failed: {proc.stderr.strip()}")
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"pile.py wrote no manifest: {exc}")
        rows = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"pile manifest line {lineno} is not valid JSON: {exc}")
    for r in rows:
        if not isinstance(r, dict):
            raise RuntimeError(f"pile manifest row is not an object: {r!r}")
        if r.get("schema") != PILE_SCHEMA:
            raise RuntimeError(
                f"pile manifest row without schema {PILE_SCHEMA}: {r!r}")
        kind = r.get("kind")
        if kind not in PILE_KINDS:
            raise RuntimeError(f"pile manifest unknown kind: {kind!r}")
        if kind == "duplicate-doc":
            copies = r.get("copies")
            if type(copies) is not int or copies < 2:
                raise RuntimeError(
                    f"pile manifest duplicate-doc with bad copies: {r!r}")
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
        # A skipped child is content, not absence: a directory whose only
        # child is __pycache__/ (or node_modules/, build/, ...) holds real
        # files and is not empty. Same treatment as .claude/worktrees below.
        skipped = [d for d in dirs if d in SKIP_DIRS]
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = Path(root).relative_to(project)
        if rel.parts[:2] == WORKTREES_PREFIX.parts:
            # A sibling session's worktree: treat as content, never as empty,
            # and do not descend into it.
            records[rel] = ([], True)
            dirs[:] = []
            continue
        records[rel] = ([rel / d for d in dirs], bool(files) or bool(skipped))
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

    File-vs-directory is read from the name, never from a trailing slash:
    a last component with a file extension names a file, so its parent
    directory is checked; anything else names the directory itself, so the
    path itself is checked. The old slash rule checked the parent for
    "work-docs/no-such-dir" (no slash, the natural prose form) and missed
    the missing directory whenever the parent existed. Checking the path
    itself also covers a missing directory named through "..".
    A path carrying a <placeholder> in its directory part cannot be
    resolved and is skipped, not failed: it names a template, not a place.
    A destination under ~ is NOT resolved against the runner's home: a home
    path names a location outside the repo, so it can never be a valid
    in-repo destination, and on a machine where ~/docs happens to exist it
    would otherwise pass. Callers must treat ~ as stale; this function never
    sees it (find_stale_destinations flags it first).
    """
    if os.path.isabs(raw):
        target = Path(raw)
    else:
        target = project / raw
    if "<" in str(target):
        return None
    if Path(target.name).suffix:
        return target.parent
    return target


def find_stale_destinations(project: Path) -> list[dict]:
    """Prompt references whose destination directory does not exist.

    Three ways to be stale: the destination directory is missing
    (reason missing_dir), the destination is a home path (reason home_path:
    destinations must name a directory inside the repo), or the prompt
    carries no machine-readable destination at all (reason no_destination:
    a prompt the check cannot parse is a prompt the check cannot verify).
    Every destination on a line is examined (finditer, not search), and the
    lead-ins match case-insensitively: a lowercase "output lands in" is
    the same lead-in, and a second destination on a line is not dropped.
    """
    stale: list[dict] = []
    prompts = project / PROMPTS_DIR
    if not prompts.is_dir():
        return stale
    for path in sorted(prompts.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        found = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in DEST_RE.finditer(line):
                found = True
                _check_one(project, path, lineno, match.group(1), stale)
        if not found:
            stale.append({
                "file": str(path.relative_to(project)),
                "line": 1,
                "destination": "(no machine-readable destination)",
                "missing_dir": "expected 'Output lands in <dir>' or "
                               "'Land as <path>'",
                "reason": "no_destination",
            })
    return stale


def _check_one(project: Path, path: Path, lineno: int, raw: str,
               stale: list[dict]) -> None:
    """One named destination: home path, missing dir, or fine."""
    # The destination often ends a sentence ("...research/."), and
    # Path() silently collapses a trailing "/." one level up, which
    # made a missing dir look present. Strip sentence punctuation first.
    destination = raw.rstrip(".,;:")
    if destination.startswith("~"):
        stale.append({
            "file": str(path.relative_to(project)),
            "line": lineno,
            "destination": destination,
            "missing_dir": "home-relative path; destinations must "
                           "name a directory inside the repo",
            "reason": "home_path",
        })
        return
    checked = _destination_dir(project, destination)
    if checked is None:
        return
    if not checked.is_dir():
        stale.append({
            "file": str(path.relative_to(project)),
            "line": lineno,
            "destination": destination,
            "missing_dir": str(checked),
            "reason": "missing_dir",
        })


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


PROVENANCE_KEYS = ("measured_on", "base_commit", "recheck_after", "follow_up")
FOLLOW_UP = ("night-rick#35: collapse the duplicate/fork backlog (#446); "
             "relocate the seven research reports (#447)")


def _baseline_payload(counts: dict[str, int], project: Path) -> dict:
    """The baseline file: counts plus provenance, validated on load."""
    import datetime
    today = datetime.date.today()
    head = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    base_commit = head.stdout.strip() if head.returncode == 0 else "unknown"
    return {
        "schema": SCHEMA,
        "counts": {k: int(counts[k]) for k in COUNT_KEYS},
        "measured_on": today.isoformat(),
        "base_commit": base_commit,
        "recheck_after": (today + datetime.timedelta(days=90)).isoformat(),
        "follow_up": FOLLOW_UP,
    }


def load_baseline(path: Path) -> dict[str, int]:
    """Load and validate the baseline. Fail closed on anything malformed.

    A baseline with the wrong schema, missing counts, a negative or
    non-integer count, or missing provenance loads as an error, never as
    zeros: a hand-edited baseline that silently redefines the ceiling is
    the same defect as a silently raised one.
    """
    if not path.is_file():
        raise FileNotFoundError(f"baseline not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"baseline is not valid JSON: {path}: {exc}")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError(f"baseline schema is not {SCHEMA}: {path}")
    counts = data.get("counts")
    if not isinstance(counts, dict):
        raise ValueError(f"baseline has no counts object: {path}")
    out: dict[str, int] = {}
    for k in COUNT_KEYS:
        v = counts.get(k)
        if type(v) is not int or v < 0:
            raise ValueError(f"baseline count {k} is not a non-negative int: {v!r}")
        out[k] = v
    for k in PROVENANCE_KEYS:
        v = data.get(k)
        if not isinstance(v, str) or not v:
            raise ValueError(f"baseline is missing provenance {k}: {path}")
    return out


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


def _outstanding(counts: dict[str, int]) -> str:
    """The known backlog, in one line, so PASS never reads as clean."""
    def n(v: int, singular: str, plural: str) -> str:
        return f"{v} {singular if v == 1 else plural}"
    parts = []
    if counts["duplicate_doc_groups"]:
        parts.append(
            f"{n(counts['duplicate_doc_groups'], 'duplicate-doc group', 'duplicate-doc groups')} "
            f"({n(counts['duplicate_doc_copies'], 'redundant copy', 'redundant copies')})")
    if counts["identical_skills"]:
        parts.append(n(counts["identical_skills"], "identical skill", "identical skills"))
    if counts["forked_skills"]:
        parts.append(n(counts["forked_skills"], "forked skill", "forked skills"))
    if counts["empty_dirs"]:
        parts.append(n(counts["empty_dirs"], "empty dir", "empty dirs"))
    if counts["artifacts"]:
        parts.append(n(counts["artifacts"], "tracked artifact", "tracked artifacts"))
    if counts["stale_destinations"]:
        parts.append(n(counts["stale_destinations"], "stale destination", "stale destinations"))
    return ", ".join(parts) if parts else "none"


def cmd_check(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve()
    baseline_path = Path(a.baseline) if a.baseline else default_baseline_path(project)
    if a.update_baseline:
        # A baseline increase is a reviewed decision, never a drive-by line
        # in a feature PR: CI must never raise the ceiling it enforces.
        if os.environ.get("CI"):
            print("repoclear check: FAIL: --update-baseline refuses under CI; "
                  "a baseline change lands as its own reviewed change from a "
                  "developer machine", file=sys.stderr)
            return 2
        result = collect(project)
        payload = _baseline_payload(result["counts"], project)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote baseline {baseline_path}: {result['counts']} "
              f"(measured {payload['measured_on']}, base {payload['base_commit'][:12]})")
        return 0
    try:
        baseline = load_baseline(baseline_path)
    except FileNotFoundError as exc:
        print(f"repoclear check: FAIL: {exc} (a missing baseline is not a pass)")
        return 2
    except ValueError as exc:
        print(f"repoclear check: FAIL: malformed baseline: {exc}")
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
    print("repoclear check: PASS: ratchet held (no growth); "
          f"known outstanding: {_outstanding(result['counts'])}")
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
        # A bare artifact at the root: no artifact segment in its path, so
        # only the suffix test can see it (this is what the suffix mutant
        # removes; the __pycache__ file is masked by the segment test).
        (proj / "stray.pyc").write_bytes(b"\x00\x01")
        prompts = proj / PROMPTS_DIR
        prompts.mkdir(parents=True)
        (prompts / "p1.md").write_text("Output lands in work-docs/no-such-dir/.\n")
        (prompts / "p2.md").write_text("Output lands in work-docs/research/.\n")
        (prompts / "p3.md").write_text("A prompt with no destination line.\n")
        (prompts / "p4.md").write_text("Output lands in ~/docs/no-such-dir/.\n")
        # A file destination ending a sentence: the rstrip is what makes
        # this a file (parent work-docs/research/ exists) rather than a
        # missing directory named "report.md.".
        (prompts / "p5.md").write_text("Land as work-docs/research/report.md.\n")
        # One identical skill pair and one forked pair, the same fixture
        # shape pile.py's own selftest uses (skill name in two payload trees).
        for tree in ("dot-claude/skills", "dot-agents/skills"):
            (proj / tree / "twin").mkdir(parents=True)
            (proj / tree / "twin" / "SKILL.md").write_text("identical\n")
            (proj / tree / "split").mkdir(parents=True)
        (proj / "dot-claude/skills" / "split" / "SKILL.md").write_text("version one\n")
        (proj / "dot-agents/skills" / "split" / "SKILL.md").write_text("version two, longer\n")
        _commit(proj)
        # B1 fixture, planted AFTER the commit so it stays untracked: a
        # directory whose only child is __pycache__/ holding a real file.
        # It is not empty and must never be reported; on the old code it
        # was reported (the skipped child counted as absent).
        (proj / "onlycache" / "__pycache__").mkdir(parents=True)
        (proj / "onlycache" / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")

        result = collect(proj)
        counts = result["counts"]
        if counts["duplicate_doc_groups"] != 1:
            fails.append(f"duplicate_doc_groups {counts['duplicate_doc_groups']}, want 1")
        if counts["duplicate_doc_copies"] != 1:
            fails.append(f"duplicate_doc_copies {counts['duplicate_doc_copies']}, want 1")
        if counts["identical_skills"] != 1:
            fails.append(f"identical_skills {counts['identical_skills']}, want 1")
        if counts["forked_skills"] != 1:
            fails.append(f"forked_skills {counts['forked_skills']}, want 1")
        if counts["empty_dirs"] != 1 or result["empty_dirs"] != ["planted"]:
            fails.append(f"empty_dirs {result['empty_dirs']}, want ['planted']")
        if counts["artifacts"] != 2 or result["artifacts"] != ["__pycache__/x.pyc", "stray.pyc"]:
            fails.append(f"artifacts {result['artifacts']}, want ['__pycache__/x.pyc', 'stray.pyc']")
        if counts["stale_destinations"] != 3:
            fails.append(f"stale_destinations {counts['stale_destinations']}, want 3")
        else:
            reasons = [(s["file"], s.get("reason")) for s in result["stale_destinations"]]
            want = [(str(PROMPTS_DIR / "p1.md"), "missing_dir"),
                    (str(PROMPTS_DIR / "p3.md"), "no_destination"),
                    (str(PROMPTS_DIR / "p4.md"), "home_path")]
            if reasons != want:
                fails.append(f"stale reasons {reasons}, want {want}")

        baseline_path = proj / "state" / "repoclear-baseline.json"
        check_args = argparse.Namespace(
            project=str(proj), baseline=str(baseline_path), update_baseline=False)
        if cmd_check(check_args) != 2:
            fails.append("check without a baseline exited non-2; a missing "
                         "baseline must fail closed, not pass")
        check_args.update_baseline = True
        # The selftest proves the update path works; the CI refusal is proven
        # by a unit test that sets CI explicitly. Without this, the selftest
        # itself would refuse its own update call when run under CI.
        saved_ci = os.environ.pop("CI", None)
        try:
            update_rc = cmd_check(check_args)
        finally:
            if saved_ci is not None:
                os.environ["CI"] = saved_ci
        if update_rc != 0:
            fails.append("--update-baseline did not exit 0")
        if cmd_check(argparse.Namespace(
                project=str(proj), baseline=str(baseline_path),
                update_baseline=False)) != 0:
            fails.append("check at exactly the baseline did not pass")
        grown = dict(counts)
        grown["duplicate_doc_groups"] = counts["duplicate_doc_groups"] - 1
        payload = _baseline_payload(grown, proj)
        baseline_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if cmd_check(argparse.Namespace(
                project=str(proj), baseline=str(baseline_path),
                update_baseline=False)) != 1:
            fails.append("check with a grown duplicate count did not fail")

        # M12: the ratchet fires on empty-dir growth too, not only on
        # duplicate growth. Lower the empty_dirs baseline by one on the
        # planted repo (which has one empty dir) and the check must fail.
        grown_empty = dict(counts)
        grown_empty["empty_dirs"] = counts["empty_dirs"] - 1
        payload = _baseline_payload(grown_empty, proj)
        baseline_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if cmd_check(argparse.Namespace(
                project=str(proj), baseline=str(baseline_path),
                update_baseline=False)) != 1:
            fails.append("check with a grown empty-dir count did not fail")

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
