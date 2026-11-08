# EXECUTION_TRACKER.md

Session execution tracker for the 2026-08-29 autonomous run on branch
`claude/autonomous-agent-execution-ik71zf` (lane A, claim row in `state/claims.jsonl`).
`TODO.md` stays the roadmap authority and `docs/PLAN-SPINE.md` the program map; this file
is the per-item execution and verification record the run maintained, per the operating
protocol that started it. Statuses: VERIFIED means the named command ran green in this
session; BLOCKED names the owner and the missing precondition; TODO points at the
roadmap row that carries it.

## Master Task Backlog

### Executed and verified this session

- [x] GATE-1 [quality-contract.json:93] Rules domain red on a waiver expired 2026-08-26
  - Status: VERIFIED
  - Acceptance Criteria: the domain measures again instead of failing on a stale waiver;
    the prior reason survives in `_waiver_history` with a removal entry
  - Verification: `python tools/gate/gate.py run --project .` reports rules PASS
    (shrink-only census, 26 rules) on this runner

- [x] GATE-2 [quality-contract.json:105] Skills domain red on a waiver expired 2026-08-26
  - Status: VERIFIED
  - Acceptance Criteria: same as GATE-1; on hosts without a deployed `~/.claude` the
    check reads N/A by the gate's own exit-2 convention, and on the live machine it
    reports the real drift list to the operator
  - Verification: gate run reports skills N/A here; removal entry in `_waiver_history`

- [x] GATE-3 [state/gate-runs.jsonl] Unit domain red: pytest absent on this container
  - Status: VERIFIED (environment provision, no repo change needed)
  - Acceptance Criteria: every test entrypoint in the unit domain chain runs green
  - Verification: root suite 650 passed, 31 skipped, 1 xfailed;
    `cd intent-control-plane && uv run pytest -q` 435 passed

- [x] GATE-4 [quality-contract.json dashboard domain] Dashboard domain red: GTK3 and
  webkit2gtk-4.1 headers absent on this container
  - Status: VERIFIED (environment provision, no repo change needed)
  - Acceptance Criteria: `cd dashboard && cargo test --workspace` exits 0
  - Verification: 16 core tests passed, src-tauri compiled and linked;
    `cd dashboard/web && bun install --frozen-lockfile && bun --bun run build` also green

- [x] PROP-1 [tools/selfimprove/proposals.jsonl, score 8] Add a test for
  `tools/setup_token_pty.py`
  - Status: VERIFIED
  - Acceptance Criteria: the module imports on any host (the PTY flow and the winpty
    import moved under `main()`), and the pure pieces are pinned: token regex shapes,
    prompt detection, and the redaction invariant that no token reaches `out.log`
  - Verification: `python -m pytest tests/test_setup_token_pty.py -q` (7 passed)

- [x] DOC-1 [tools/setup_token_pty.py:5] Docstring claimed a `#state` suffix strip the
  code never performed
  - Status: VERIFIED (docstring corrected to match behavior; behavior unchanged on
    purpose, because the auth flow only runs on the operator's Windows machine and a
    behavior change there is not verifiable from this host)
  - Verification: the docstring now says the code is fed verbatim minus surrounding
    whitespace, which is what `read_text().strip()` does

- [x] TEST-1 [tests/test_capture_turn_enrichment.py:53] Suite runs were appending
  hashed "test-session" rows to the real `state/prompt-tickets.jsonl`
  - Status: VERIFIED
  - Acceptance Criteria: the hook tests keep their caller reproduction (system
    interpreter, scrubbed env) but the durable row lands in a fixture-owned ledger;
    the six rows this session's runs appended are not committed
  - Verification: `python -m pytest tests/test_capture_turn_enrichment.py -q` passes
    and `git status -s state/prompt-tickets.jsonl` stays empty afterward; found because
    capture_turn.py resolves REPO_ROOT from its own file path, so the fixture copies
    the three trees the hook resolves into tmp and runs the copy

- [x] SESS-1 [docs/SESSION-BOOT.md:6] Lane named and claimed before starting
  - Status: VERIFIED
  - Verification: lane A claim row dated 2026-08-29 in `state/claims.jsonl`

- [x] GATE-5 Full contract green on this tree
  - Status: VERIFIED
  - Verification: `python tools/gate/gate.py run --project .` VERDICT PASS, recorded in
    `state/gate-runs.jsonl`; supporting checks also green this session:
    `codemap.py check`, `pointers.py scan`, `refute.py run` (16 held, 0 refuted),
    `books_check.py`, `coverage_map.py check`

### Blocked: owner is the operator or the live machine

- [ ] BLK-1 [quality-contract.json rules history] Curate which live edits of
  `gastown-company-registry.md` fold back into the repo (live 12042b vs repo 8495b)
  - Status: BLOCKED (operator content decision; needs the live `~/.claude/rules` tree)
  - Verification when done: `python tools/audit/rules_sync.py check` exits 0 on the
    operator's machine with drift measured, not skipped

- [ ] BLK-2 [quality-contract.json skills history] Pick a side per drifted skill file
  (33 items at last live measurement, direction not uniform)
  - Status: BLOCKED (operator content decision; the 2026-08-23 session's own
    recommendation is to resolve it from the live machine, and this run kept that)
  - Verification when done: `python tools/audit/skills_sync.py check` exits 0 live

- [ ] BLK-3 [TODO.md:105, R-1] Rotate the API key exposed in the pushed history of
  `e695af5`
  - Status: BLOCKED (operator credential action; history rewrite denied to assistants
    on purpose)
  - Verification when done: the operator records the rotation; the old value is dead

- [ ] BLK-4 [tools/intent/render_todo.py] TODO.md lost its generated prompt-inbox block
  (`render_todo.py check` reports DRIFT: no generated block)
  - Status: BLOCKED (needs the real `~/.intent/intent.db` store; rendering from this
    host would write an empty inbox over a store holding 354 captured tickets)
  - Verification when done: `python tools/intent/render_todo.py check` exits 0 on the
    live machine after `write`

- [ ] BLK-5 [TODO.md R-2] A green Ship gate run on the self-hosted runner for this
  branch's PR
  - Status: BLOCKED here, expected to clear on push (CI runs on the operator's runner;
    rules will measure real drift there, see BLK-1, and skills likewise BLK-2, so the
    gate job's verdict on the runner depends on those operator decisions)
  - Verification: the PR's Ship gate check on the current head

- [x] PROP-2 [tools/selfimprove/proposals.jsonl, score 8] Add a test for
  `tools/slop_lint.py`
  - Status: VERIFIED
  - Acceptance Criteria: every scan category (banned phrases, em/en-dash connectors,
    ritual acknowledgements, ritual openers) fires on its own representative, clean
    prose stays clean, line numbers are correct, the collector never fails the run,
    and main() exits 1 on hits and 0 on clean
  - Verification: `python -m pytest tests/test_slop_lint.py -q` (18 passed);
    root suite 675 passed

- [x] AUTO-06 [docs/specs/2026-07-24-autonomy-implementation.md P1] Ecosystem state DB
  - Status: VERIFIED
  - Acceptance Criteria: `tools/eco/db.py` implements the 7-table schema from ADR-0011,
    init/migrate-jsonl/claim/log-run/approve/status/selftest subcommands all work, JSONL
    migration ingests from state/lessons.jsonl (57 rows), state/claims.jsonl (26 sessions),
    and tools/selfimprove/proposals.jsonl (3 proposals), schema constraints enforce valid
    status/kind/autonomy values, double-claim is rejected, idempotent re-migration is safe
  - Verification: `python tools/eco/db.py selftest` PASS; `python -m pytest
    tests/test_eco_db.py -q` (20 passed); root suite 695 passed, 31 skipped, 1 xfailed

- [x] CORPUS-1 [docs/specs/2026-07-31-research-corpus-and-cache.md steps 1-4] Research
  corpus DB with FTS5 search
  - Status: VERIFIED
  - Acceptance Criteria: `tools/corpus/research.py` implements the 6-table + FTS5 schema
    from spec section 4.3, 4-stage ingestion pipeline (normalise, chunk, dedup, citation
    gate), FTS5 query with BM25 ranking, defect queries for uncited and contradicted chunks,
    CLI with init/ingest/query/defects/status/selftest subcommands
  - Verification: `python tools/corpus/research.py selftest` PASS; `python -m pytest
    tests/test_corpus_research.py -q` (31 passed); ingest over 365 sources produces 5936
    chunks with 3618 citations and 68 exact duplicates; FTS5 search returns ranked results;
    root suite 726 passed, 31 skipped, 1 xfailed; full 12-domain gate PASS

### Open roadmap backlog, tracked where it lives

The roadmap rows below stay owned by `TODO.md` sections 1 through 3 and the issue
checklist referenced by `state/prompt-tickets.jsonl` triage; this run re-verified they
are visible, not silently dropped. Long-horizon rows (KR-4 review fabric, KR-5 weekly
self-improvement loop, KR-6 skills estate, KR-8 WhatsApp copilot, KR-9 learning-card
emitter, KR-10 scheduler consolidation, the AUTO lane slice, the DASH adoption
evaluation) each name their own acceptance in `CLAUDE-OS.md` section 9 and are not
executable from an ephemeral container without the operator's machines, keys, or
schedulers; they are deliberately not duplicated into checkboxes here, because a second
checklist that drifts from the roadmap is the exact failure `docs/archive/MIGRATION-NOTES.md`
records. The remaining selfimprove proposals not executed: "Return to main" does
not apply (this session is bound to its feature branch by its operating instructions),
and "Grow flywheel" needs live router traffic this host does not carry.
