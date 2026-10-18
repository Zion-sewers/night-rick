"""Tests for the per-project TODO renderer.

The load-bearing property is that a generated block never eats hand-written text. This
repository's own TODO.md is 691 lines carrying reasoning that exists nowhere else, and
the lifecycle spec names regenerating it as the failure the whole design avoids.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "intent"))

import render_todo as rt  # noqa: E402
import tickets  # noqa: E402


def ticket(tid, text, repo="/x/demo", state="CAPTURED", ts="2026-08-01T00:00:00Z",
           session="s1"):
    return {"ticket": tid, "session": session, "repo": repo, "ts": ts, "text": text,
            "goal": text[:60], "state": state}


def test_selftest_passes():
    assert rt.selftest() == 0


@pytest.mark.parametrize("path,expected", [
    ("C:\\Users\\shova\\Downloads\\new-recruit", "new-recruit"),
    ("/home/shov/work/repos/new-recruit", "new-recruit"),
    ("/mnt/c/Users/shova/claude-setup", "claude-setup"),
    ("/home/shov/work/repos/daily-deep-learning/daemon", "daily-deep-learning/daemon"),
    ("", ""),
])
def test_project_key_survives_both_spellings(path, expected):
    assert rt.project_key(path) == expected


def test_the_windows_and_wsl_paths_of_one_repo_are_one_project():
    """The estate moved OS mid-history. Full-path matching would halve every count."""
    rows = [ticket("PT-a", "old", repo="C:\\Users\\shova\\Downloads\\new-recruit"),
            ticket("PT-b", "new", repo="/home/shov/work/repos/new-recruit")]
    assert len(rt.for_project(rows, "/anywhere/new-recruit")) == 2


def test_a_generic_leaf_keeps_its_parent():
    rows = [ticket("PT-a", "x", repo="/a/daily-deep-learning/daemon"),
            ticket("PT-b", "y", repo="/b/unrelated/daemon")]
    assert len(rt.for_project(rows, "/c/daily-deep-learning/daemon")) == 1


def test_summarize_splits_noise_from_untriaged():
    rows = [ticket("PT-a", "rewrite the parser"), ticket("PT-b", "/compact"),
            ticket("PT-c", "yes"), ticket("PT-d", "ship it", state="OPEN")]
    s = rt.summarize(rows)
    assert s["noise"] == 2, "a bare slash command and an ack are rule-classified"
    assert [r["ticket"] for r in s["untriaged"]] == ["PT-a"]
    assert [r["ticket"] for r in s["workable"]] == ["PT-d"]


def test_triaged_tickets_render_as_issue_pointers_not_a_blank_inbox():
    """2026-08-23: after every ticket was triaged the block said '0 workable, 0 awaiting'
    and nothing else, which hid where 354 prompts had gone."""
    a = dict(ticket("PT-a", "fix the launcher", state="TRIAGED"),
             reason="prompt-triage 2026-08-23: T04 -> issue #94")
    b = dict(ticket("PT-b", "kitty errors", state="TRIAGED"),
             reason="prompt-triage 2026-08-23: T04 -> issue #94")
    c = dict(ticket("PT-c", "buzz tui", state="TRIAGED"),
             reason="prompt-triage 2026-08-23: T05 -> issue #95")
    d = dict(ticket("PT-d", "y go", state="NOT_WORK"), reason="ack")
    s = rt.summarize([a, b, c, d])
    assert s["triaged"] == {"#94": 2, "#95": 1}
    assert s["not_work"] == 1
    block = rt.render("/x/demo", [a, b, c, d])
    assert "- #94: 2 prompts" in block
    assert "1 prompts were marked not work" in block


def test_splice_preserves_hand_written_text(tmp_path):
    todo = tmp_path / "TODO.md"
    handwritten = "# TODO\n\n- [ ] load-bearing hand-written item\n\n## A section\n\nbody\n"
    todo.write_text(handwritten, encoding="utf-8")
    block = rt.render("/x/demo", [ticket("PT-a", "rewrite the parser")])

    todo.write_text(rt.splice(todo.read_text(), block), encoding="utf-8")
    after = todo.read_text()
    assert handwritten in after
    assert "rewrite the parser" in after


def test_splice_is_idempotent_and_leaves_one_marker_pair(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# TODO\n", encoding="utf-8")
    block = rt.render("/x/demo", [ticket("PT-a", "something")])
    once = rt.splice(todo.read_text(), block)
    assert rt.splice(once, block) == once
    assert once.count(rt.BEGIN) == 1
    assert once.count(rt.END) == 1


def test_a_second_render_replaces_rather_than_appends(tmp_path):
    first = rt.splice("# TODO\n", rt.render("/x/demo", [ticket("PT-a", "first prompt")]))
    second = rt.splice(first, rt.render("/x/demo", [ticket("PT-b", "second prompt")]))
    assert "first prompt" not in second
    assert "second prompt" in second
    assert second.count(rt.BEGIN) == 1


def test_rule_classified_prompts_are_counted_never_listed():
    block = rt.render("/x/demo", [ticket("PT-a", "/compact"), ticket("PT-b", "y")])
    assert "/compact" not in block
    assert "2 classified as slash commands or acks by rule" in block


def test_the_cap_states_what_it_dropped():
    rows = [ticket(f"PT-{i}", f"prompt number {i}", ts=f"2026-08-01T00:00:{i:02d}Z")
            for i in range(rt.TRIAGE_WINDOW + 5)]
    block = rt.render("/x/demo", rows)
    assert f"newest {rt.TRIAGE_WINDOW} of {len(rows)}" in block
    assert "5 older untriaged prompts are not listed here" in block


def test_an_empty_project_says_so_rather_than_rendering_nothing():
    block = rt.render("/x/empty", [])
    assert "No prompt tickets recorded" in block
    assert rt.BEGIN in block and rt.END in block


def test_the_block_carries_the_operators_words_not_a_paraphrase():
    text = "this repo is messy. how much you know of it ?"
    assert text in rt.render("/x/demo", [ticket("PT-a", text)])


def test_check_fails_on_an_edited_block(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# TODO\n", encoding="utf-8")
    block = rt.render("/x/demo", [ticket("PT-a", "original")])
    todo.write_text(rt.splice(todo.read_text(), block), encoding="utf-8")
    tampered = todo.read_text().replace("original", "hand edited")
    assert rt.splice(tampered, block) != tampered


def test_render_never_promotes_a_ticket():
    """The renderer reports states; it must not be able to change one."""
    source = (REPO_ROOT / "tools" / "intent" / "render_todo.py").read_text()
    for verb in ("insert into state_transitions", "advance(", "record_transition"):
        assert verb not in source, f"render_todo can {verb}; it may only read"


def test_resolve_project_follows_a_worktree_to_its_repository():
    here = Path(__file__).resolve().parent
    # Repo renamed claude-setup -> night-rick 2026-10-18; the project key
    # follows the live repo name.
    assert rt.project_key(str(rt.resolve_project(here))) == "night-rick"


def test_load_of_an_absent_store_is_empty_not_an_error(tmp_path):
    assert rt.load(tmp_path / "nothing-here") == []
