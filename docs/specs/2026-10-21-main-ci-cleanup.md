# Main CI Cleanup (2026-10-21)

**Date:** 2026-10-21
**Status:** active

## Problem

`main` was red since 2026-10-13 on two ship-gate jobs, blocking the entire PR
queue. Fixing the two diagnosed failures unmasked seven more latent failures
in `gate.py run` plus a drifted mutation spec — all pre-existing, all masked
because the job died before reaching them.

## Solution

### Diagnosed failures (PR #440, first commit)

1. `gate` / `strand.py check`: 27 `docs/specs/2026-08-31-corpus-*` files
   unreachable outside `docs/INDEX.md`. They are imported corpus analysis
   profiles (evidence, read by tooling), so they were carried as exempt debt
   in `docs/strand-exempt.txt` with one-line reasons, per the check's own
   suggested remedy and the 2026-08-05 import precedent in the same file.
2. `falsifiability` / `skilleval scan`: `create-verification-skill` SKILL.md
   had its MIT attribution line ahead of the frontmatter, so the parser
   (requires `---` at byte 0) saw no name/description and nothing routed to
   it. Moved the attribution below the frontmatter; attribution preserved.

### Latent failures unmasked (second commit)

3. `prose_fit`: refit stale thresholds (corpus 256 → 533 scores) via
   `prose_fit.py fit`.
4. `codemap`: regenerated `docs/CODEBASE-MAP.md`; added the missing
   `.github/agent-coffee` purpose row to `docs/dir-purpose.txt`.
5. `docmap`: regenerated `docs/DOCMAP.md`; declared `Status:` for 9
   undeclared documents in `docs/doc-status.txt` (`living` for active docs,
   `dated-snapshot` for the two September research notes, `operator-input`
   for the Hebrew install note).
6. `prior_art`: re-ran the whatsapp recheck. Local legs verified (0 callers;
   the one grep hit is a vendored generic CDP driver, not a caller;
   `cdp_driver.py` still fails with ModuleNotFoundError). Upstream leg
   verified via live fetch of the Meta Groups API docs (2026-10-21): OBA-only,
   excludes WhatsApp Business app numbers. Verdict `delete-ours` holds;
   `recheck_after` moved to 2026-11-21.
7. `coverage_map`: declared `anatomy` as `covered-by:review` (panel.py's
   diff-level E-row checks read `anatomy/e-rows/`).
8. `unit`: updated stale `claude-setup` expectations to `night-rick` in
   `render_todo.py` selftest and `test_render_todo.py` (repo rename
   2026-10-18).
9. `skip_tracker`: handle a missing `uv` binary gracefully (warning + skip
   suite) instead of crashing with FileNotFoundError.
10. `mutate.py --spec all`: two gate-spec mutation patterns had drifted
    (`if waiver.get("confirm"):` and the old FAIL string no longer exist in
    `gate.py` after the `confirm_waiver` refactor). Updated to the current
    code; both verified caught by the selftest.

## Scope

- `docs/strand-exempt.txt`, `dot-claude/skills/create-verification-skill/SKILL.md`
- `state/prose-thresholds.json`, `docs/CODEBASE-MAP.md`, `docs/DOCMAP.md`
- `docs/doc-status.txt`, `docs/dir-purpose.txt`, `docs/coverage-map.txt`
- `docs/prior-art/tools-whatsapp.json`
- `tests/test_render_todo.py`, `tools/intent/render_todo.py`
- `tools/audit/skip_tracker.py`, `tools/audit/mutations/gate.py`
- This spec file

## Design decisions

- Exempt rather than link the 27 corpus specs: they are evidence read by
  tooling, and 27 links from the read surface would add noise, not reach.
- Registry rows (not `Status:` lines) for the 9 docs: the registry is the
  designed mechanism for residue the class rules cannot derive.
- Re-ran the whatsapp recheck fully (both local legs + live page fetch)
  rather than waiving: the expiry mechanism exists to force re-verification,
  and the verdict's flip condition (Cloud API Groups scope) is checkable.
- Updated the drifted mutation patterns rather than deleting the mutations:
  the waiver-confirmation behavior they guard still exists in `confirm_waiver`.

## Non-goals

- Fixing the underlying reasons the maps went stale (no owner runs `write`
  after doc changes). That is a process gap, not a code defect.
- The `test_trycmd` ordering flake seen once locally (passes in isolation
  and in full-suite reruns); not reproduced reliably enough to fix.
