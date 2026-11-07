# Repo Clear gate domain (night-rick#35)

**Date:** 2026-11-07
**Status:** active

## Problem

night-rick#35 (EPIC: Repo Clear, an enforced standard rather than a written
one) observes that a prose standard rots: the survey found 502 dirs / 11
empty / 1037 md / 106 byte-identical duplicates / 38 agent files in
claude-setup alone, and a lane declared in work-docs/research/README.md that
the actual files ignore. The epic's own prescription is a checker with a gate
domain, not another document.

Two halves of that prescription already existed in un-enforced form:

1. `tools/audit/pile.py` detects byte-identical documents and skill
   copies/forks, with a selftest and a mutation spec. Nothing gates on its
   report: only its selftest runs, in the falsifiability job. A real oracle
   reporting into a terminal nobody gates on.
2. The 2026-07-27 research prompts name `~/docs/research/` as their output
   destination. That path does not exist; the seven reports landed in
   work-docs/ root under prose titles. Nothing checked the destination.

## Solution

### tools/repoclear/scan.py (new, stdlib only)

Four detectors, one report, read-only (`scan` / `check` never write, move,
or delete anything):

- **duplicates**: counts read from pile.py's manifest (`scan --out`), not
  re-implemented. One owner per detection. Reports duplicate-doc groups,
  redundant copies, identical skills, forked skills.
- **empty_dirs**: filesystem walk, because git never tracks an empty
  directory. Topmost empty directory per empty subtree; `.git`, virtualenvs,
  `node_modules`, `target/`, `dist/`, `build/`, and `.claude/worktrees`
  (sibling sessions' trees) are excluded.
- **artifacts**: tracked files matching build-artifact patterns
  (`__pycache__/`, `*.pyc`, `node_modules/`, `.venv/`, `target/`, ...).
- **stale_destinations**: `work-docs/research/prompts/*.md` lines of the
  form `Output lands in X` / `Land as X`; the destination DIRECTORY must
  exist (a prompt may name a file that does not exist yet). Sentence
  punctuation is stripped before resolving: `Path` collapses a trailing
  `/.` one level up, which made a missing dir look present until the
  selftest caught it.

### The ratchet, not the cleanup

`check` fails when any count grows past `state/repoclear-baseline.json`
(skip_tracker.py precedent). Measured on main 2026-11-07: 2 duplicate-doc
groups (2 redundant copies), 19 identical skills, 38 forked skills, 0 empty
dirs, 0 tracked artifacts, 0 stale destinations. A missing baseline fails
closed (exit 2), never passes. Collapsing the existing duplicate/fork
backlog is follow-up work (#92 / PR #444 and a dedup unit); this domain
stops the pile growing.

### Wiring

- `quality-contract.json`: required domain `repoclear`,
  `python tools/repoclear/scan.py check`, timeout 300. No gate.py change:
  extra contract domains run by the "DOMAINS is the floor, not the ceiling"
  rule, same as `dashboard` / `coverage_map`.
- `tools/audit/mutations/repoclear.py`: 5 mutants, each caught by
  `mutate.py --spec all` (empty-dir blind, artifact blind, baseline
  comparison inverted, stale-destination resolver accepting missing paths,
  duplicate groups dropped).
- `tests/test_repoclear.py`: detectors on planted synthetic git repos, the
  ratchet (pass at baseline, fail on growth, exit 2 on missing baseline),
  and two pins: the contract declares the domain, the committed baseline
  matches the live tree.
- `ship-gate.yml` falsifiability: named `repoclear selftest` step.
- `docs/dir-purpose.txt`: row for `tools/repoclear/` (codemap domain).
- Prompt fixes: the seven 2026-07-27 prompts + README now name
  `work-docs/research/` (the directory that exists). The seven existing
  reports stay in work-docs/ root under their prose titles; relocating them
  is curation, named as follow-up.

## Deliberately out of scope

- The epic's four-repo report: the other repos are not checked out in CI,
  so the scanner reports over the repo it runs in (`--project`).
- Task 2 (one root AGENTS.md per repo): covered by #92, in flight as
  PR #444.
- Task 5 (new-recruit dedup): a different repo.
- Task 6 (WSL2 move): epic-level.
- Closing #35 itself: Shoval 2026-08-23: the epic stays open on purpose
  and closing it is the operator's call once the boxes it covers are done.
  The PR references #35 (`Refs #35`), it does not close it.
