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
   destination. That path does not exist; the six reports landed in
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
  (sibling sessions' trees) are excluded. A skipped child counts as
  content, not absence: a directory whose only child is `__pycache__/` (or
  `node_modules/`, `build/`, ...) holding real files is not empty.
- **artifacts**: tracked files matching build-artifact patterns
  (`__pycache__/`, `*.pyc`, `node_modules/`, `.venv/`, `target/`, ...).
  Matching is case-insensitive, and `git ls-files` runs `-z` so non-ASCII
  filenames survive quoting. The segment test is deliberately broad by
  design: any directory named `build/` (or `dist/`, `target/`, ...) is an
  artifact container. Narrowing it is follow-up work (#450), not a silent
  fix: a future legitimate `docs/build/guide.md` would fail the gate as a
  tracked build artifact under the current test.
- **stale_destinations**: `work-docs/research/prompts/*.md` lines of the
  form `Output lands in X` / `Land as X`; the destination DIRECTORY must
  exist (a prompt may name a file that does not exist yet). File-vs-directory
  is read from the name, never from a trailing slash: a last component with
  a file extension names a file, so its parent is checked; anything else
  names the directory itself. Sentence punctuation is stripped before
  resolving: `Path` collapses a trailing `/.` one level up, which made a
  missing dir look present until the selftest caught it. Every destination
  on a line is examined, and the lead-ins match case-insensitively. The
  check validates directory existence ONLY: it does not prove reports land
  there (the six reports are still in work-docs/ root; relocating them is
  #447). A destination under `~` is unresolvable inside the repo and counts
  as stale (it is never expanded against the runner's home), and so does any
  destination that resolves outside the repo (an absolute path, or a `..`
  path that escapes it): destinations must name a directory inside the repo.
  A prompt with no machine-readable destination counts as stale too: a
  prompt the check cannot parse is a prompt the check cannot verify.

Detector scopes, stated so they can be argued with: duplicates and tracked
artifacts are computed from `git ls-files` (tracked files only), while
empty dirs are computed from a filesystem walk (tracked, untracked, and
ignored alike, minus `SKIP_DIRS`). A clean CI checkout and a dirty
developer tree therefore measure the same tracked counts but can differ on
empty dirs: run the gate and the pin test on a clean tree, because an empty
directory can never be committed, so the empty-dir half of the gate polices
working-tree state, not the commit.

### The ratchet, not the cleanup

`check` fails when any count grows past `state/repoclear-baseline.json`
(skip_tracker.py precedent). Measured on main 2026-11-07: 2 duplicate-doc
groups (2 redundant copies), 19 identical skills, 38 forked skills, 0 empty
dirs, 0 tracked artifacts, 0 stale destinations. A missing or malformed
baseline fails closed (exit 2), never passes. The baseline file carries
provenance (`measured_on`, `base_commit`, `recheck_after`, `follow_up`),
validated on load, so a bump is distinguishable from the original
measurement. A baseline increase is a reviewed decision, never a drive-by
line in a feature PR: `check --update-baseline` refuses under CI and on a
dirty tracked tree, the baseline file carries provenance validated on load
for shape (dates must parse as dates, `base_commit` must be a 40-hex sha),
and CI runs `tools/repoclear/baseline_guard.py`, which fails a PR that
modifies the committed baseline alongside other files (a baseline that is
newly added, or changed alone, passes: that is the reviewed decision). The
guard closes the drive-by path, not the reviewed path: a hand-edit that
lands alone still relies on review, and the spec says so rather than
claiming otherwise. The PASS line names the outstanding backlog every time
("ratchet held (no growth); known outstanding: ..."), so green never reads
as clean. Collapsing the existing duplicate/fork backlog is follow-up work
(#446); this domain stops the pile growing.

The pile.py seam is fail-closed: every manifest row must carry schema
`pile.v1` and a known kind, and a duplicate-doc row must carry `copies` of
at least 2, or the run raises instead of counting zero; a malformed manifest
line and a pile.py timeout raise the same way. A zero-row manifest
is legitimate (a clean repo emits no rows), so kinds are validated when
present, not required; the selftest plants one group of each kind and
asserts the counts, so a pile.py that silently stopped seeing groups goes
red there. Known limitation, stated not hidden: a pile.py that emits zero
rows on a dirty repo reads as a clean repo in `check` itself; the backstop
is the selftest (which plants groups) and the equality pin test
(`test_committed_baseline_matches_live_tree`, which fails when the live tree
stops measuring exactly the baseline), not the check. The seam's own
dependency is the least hardened part of the chain: `pile.py`'s `git_files`
ignores its return code and has no timeout, so a git failure inside pile.py
silently returns no groups; until that is hardened, the pin test is the
reliance and this paragraph is where it is recorded. Timeouts are set from
the measured runtime (about 2s total on main): the contract allows 60s,
pile.py gets 30s, git gets 15s, so the composed worst case (45s) sits below
the outer timeout.

`tools/repoclear/` is a directory, not a flat file under `tools/audit/`,
because the tool is a subsystem (scanner plus ratchet state plus selftest
plus mutation spec), not a single-purpose checker like `pile.py`. Its
exclusion lists (`SKIP_DIRS`, `ARTIFACT_SEGMENTS`) are local copies, not
shared with pile.py. The honest reason is size, not coupling: the lists are
small, and the scanner already has a hard runtime coupling to audit tooling
(it shells out to `tools/audit/pile.py` on every run), so "import-free"
would be a false justification for keeping them apart. The drift the split
invites is pinned by a test (`tests/test_repoclear.py` asserts the
scanner's `SKIP_DIRS` covers pile.py's): pile's set is
`{__pycache__, .git, node_modules, .venv}` and the scanner's is a superset
of it. Sharing one exclusion list is adoption work, not this unit.

Mutation coverage, stated honestly: `mutate.py --spec repoclear` runs with
`ARGV = ["selftest"]`, so it covers what the selftest exercises (each
detector going blind, the comparison inverting and off by one, the copies
arithmetic, the identical/forked drops, the artifact suffix drop, the
sentence-punctuation strip, the outside-repo containment drop, the empty
skipped child counting as content). It does not cover `check
--update-baseline` or `scan --json`, which the selftest does not reach;
those paths are covered by `tests/test_repoclear.py` instead. It also does
not cover the pile-seam validation itself (schema/kind/copies checks): a
mutant dropping the schema check would survive, because the selftest plants
a valid manifest and the counts would be unchanged; that validation is
unit-test-covered only (`test_manifest_validation_fails_closed`,
`test_malformed_manifest_line_fails_closed`,
`test_pile_timeout_fails_closed`).

### Wiring

- `quality-contract.json`: required domain `repoclear`,
  `python tools/repoclear/scan.py check`, timeout 60 (from the measured
  runtime, about 2s total). No gate.py change: extra contract domains run by
  the "DOMAINS is the floor, not the ceiling" rule, same as `dashboard` /
  `coverage_map`.
- `tools/audit/mutations/repoclear.py`: 13 mutants, each caught by
  `mutate.py --spec all` (empty-dir blind, artifact blind, baseline
  comparison inverted, ratchet comparison off by one, stale-destination
  resolver accepting missing paths, sentence punctuation not stripped,
  artifact suffix dropped, duplicate groups dropped, identical skills
  dropped, forked skills dropped, duplicate copies arithmetic off by one,
  outside-repo containment dropped, empty skipped child counting as
  content).
- `tests/test_repoclear.py`: detectors on planted synthetic git repos
  (including identical/forked skill fixtures), the ratchet (pass at baseline,
  fail on growth in duplicates and in empty dirs, exit 2 on missing or
  malformed baseline, --update-baseline refusing under CI, PASS line naming
  the outstanding backlog), manifest validation failing closed (bad schema,
  unknown kind, bad copies, malformed line, pile timeout), and two pins:
  the contract declares the domain, the committed baseline matches the live
  tree.
- `ship-gate.yml` falsifiability: named `repoclear selftest` step.
- `docs/dir-purpose.txt`: row for `tools/repoclear/` (codemap domain).
- Prompt fixes: the seven 2026-07-27 prompts + README now name
  `work-docs/research/` (the directory that exists), 18 stale destinations
  fixed to 0 (15 home-path references + 3 prompts with no machine-readable
  destination); the three 2026-07-12 prompts had no machine-readable
  destination at all (their output statements named `~/docs/` in other
  words) and now name `work-docs/research/` too. The six existing
  reports stay in work-docs/ root under their prose titles; relocating them
  is #447.

## Deliberately out of scope

- The epic's four-repo report (task 1 asks for one report over the four
  repos): the scanner is night-rick only today. The other repos are not
  checked out in CI and have no pile.py, no repoclear domain, and no
  baseline; porting means copying the tool, the contract domain, and a
  measured baseline, not just passing `--project`.
- Task 2 (one root AGENTS.md per repo): covered by #92, in flight as
  PR #444.
- Task 5 (new-recruit dedup): a different repo.
- Task 6 (WSL2 move): epic-level.
- Closing #35 itself: Shoval 2026-08-23: the epic stays open on purpose
  and closing it is the operator's call once the boxes it covers are done.
  The PR references #35 (`Relates to #35`), it does not close it.

Task mapping, so the scope claim is checkable without opening the epic:
task 1 is the scanner, task 3 is the gate domain with its selftest and
mutation spec, task 4 is the research-path fix. Follow-ups are tracked
issues, not PR-body prose: #446 (collapse the duplicate/fork backlog),
#447 (relocate the six research reports), #448 (recheck the 41 expired
prior-art records), #449 (Ship gate failing at actions/setup-python@v5 on
vm-runner-01), #450 (narrow the artifact segment test).
