"""night-rick#5: reconcile the contradictions the repo states about itself.

Each task in state/github-backlog-2026-07-31.json epics[1] was re-verified against
current main (2026-11-09, 2e307e66). Seven tasks are dead or already corrected; three
needed a correcting row appended to state/claims.jsonl (never a rewrite, per the
repo's own convention). This test pins the verdicts so a future regeneration cannot
silently resurrect a resolved contradiction:

  - rows 1, 2, 5, 8, 10 are dead: the file no longer asserts what the task says it does.
  - row 9 was already corrected by the dated block in docs/SYSTEM-MAP.md (2026-07-31).
  - rows 3, 4, 6 are corrected by appended claims.jsonl rows (proposal_ids below).

The archived HANDOFF and the July-29 audit doc are historical records: this test
asserts they still carry the stale figures (history preserved) AND that the
correction rows exist (correction recorded, not rewritten).
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORRECTION_IDS = {
    "lane-b": "correction-2026-11-09-issue-5-lane-b",
    "verdicts-993": "correction-2026-11-09-issue-5-993-verdicts",
    "handoff-9pct": "correction-2026-11-09-issue-5-handoff-9pct",
}


def _tracked(pattern):
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", pattern],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.splitlines()


def _claims_rows():
    rows = []
    for line in (ROOT / "state" / "claims.jsonl").read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_root_claude_md_is_tracked():
    # Task 1: "Root CLAUDE.md is UNTRACKED" , dead; it is tracked.
    assert "CLAUDE.md" in _tracked("CLAUDE.md")


def test_claude_md_carries_no_test_count_claim():
    # Task 2: "CLAUDE.md claims 70 tests" , dead; no test-count claim remains.
    assert "70 tests" not in (ROOT / "CLAUDE.md").read_text()


def test_index_line_8_carries_no_lane_letters():
    # Task 5: "docs/INDEX.md line 8 still describes the pre-ADR-0016 lane letters" ,
    # dead; line 8 carries no lane-letter description.
    lines = (ROOT / "docs" / "INDEX.md").read_text().splitlines()
    assert "lane" not in lines[7].lower()


def test_correction_rows_present_in_claims_ledger():
    # Tasks 3, 4, 6: the three live corrections must be appended rows, never rewrites.
    by_id = {}
    for row in _claims_rows():
        pid = row.get("proposal_id") or row.get("id")
        if pid:
            by_id[pid] = row
    for key, pid in CORRECTION_IDS.items():
        assert pid in by_id, f"missing correction row {pid} ({key})"
        assert by_id[pid]["lane"] == "A"
        assert (by_id[pid].get("date") or by_id[pid].get("ts")) == "2026-11-09"
    text_993 = by_id[CORRECTION_IDS["verdicts-993"]].get("claim") or by_id[CORRECTION_IDS["verdicts-993"]].get("note") or ""
    assert "59" in text_993 and "748" in text_993 and "1648" in text_993
    text_handoff = by_id[CORRECTION_IDS["handoff-9pct"]].get("claim") or by_id[CORRECTION_IDS["handoff-9pct"]].get("note") or ""
    assert "31%" in text_handoff and "74" in text_handoff


def test_archived_handoff_not_rewritten():
    # Task 6: the archived handoff is a point-in-time record; the stale sentences stay
    # (history preserved) and the correction lives in claims.jsonl instead.
    text = (ROOT / "docs" / "archive" / "HANDOFF-2026-07-30-overnight-run.md").read_text()
    assert "Phase A5" in text
    assert "9%" in text


def test_system_map_correction_block_present():
    # Task 9: the five false VERIFIED rows were already corrected by a dated block.
    text = (ROOT / "docs" / "SYSTEM-MAP.md").read_text()
    assert "## CORRECTION 2026-07-31" in text


def test_quality_contract_domain_count_moved_on():
    # Task 8: "CLAUDE.md says 'the full 12-domain contract'; quality-contract.json
    # declares 13" , dead on both sides; the contract now declares 33 domains.
    assert "domain" not in (ROOT / "CLAUDE.md").read_text().lower()
    contract = json.loads((ROOT / "quality-contract.json").read_text())
    assert isinstance(contract["domains"], dict)
    assert len(contract["domains"]) > 13


def test_handoff_nine_percent_stale_by_current_counts():
    # Task 6: the handoff's "309 documents" denominator is stale , the estate is bigger.
    docs_md = _tracked("docs/*.md")
    assert len(docs_md) > 309


def test_backlog_tasks_all_marked_done():
    # Every task in the JSON epic carries a dated DONE verdict with evidence.
    backlog = json.loads((ROOT / "state" / "github-backlog-2026-07-31.json").read_text())
    epic = next(
        e for e in backlog["epics"] if "contradictions" in e["title"].lower()
    )
    assert len(epic["tasks"]) == 10
    for task in epic["tasks"]:
        assert task.startswith("DONE 2026-"), f"unresolved task: {task[:80]}"
