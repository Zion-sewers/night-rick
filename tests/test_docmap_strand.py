# -*- coding: utf-8 -*-
"""Regression tests for tools/docmap/strand.py.

The selftest inside the tool proves both rules can fire. These tests pin the
parser behaviours that were WRONG on the first real run, so a future edit that
re-breaks them turns red here rather than being discovered by reading a report.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "docmap"))
import strand  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(REPO / "tools/docmap/strand.py"), "selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_frontmatter_status_is_read():
    assert strand.declared_status("---\nstatus: proposed\n---\n\n# X\n") == "proposed"


def test_body_status_line_is_read():
    assert strand.declared_status("# X\n\nStatus: DESIGN, 2026-08-03. Nothing built.\n") == "design"


def test_superseded_by_target_is_a_declared_status():
    """`Status: superseded by <file>` carries its target and is still `superseded`.

    First real run reported this as an unknown status, which is the oracle
    checking its own ruled form instead of the property (L-2026-07-31-b).
    """
    got = strand.declared_status(
        "# X\n\nStatus: superseded by 2026-07-29-architecture-build-plan-v2.md the same day.\n")
    assert got == "superseded"


def test_status_with_a_scope_clause_is_the_bare_status():
    got = strand.declared_status(
        "# X\n\n- Status: APPROVED for autonomous execution (operator, 2026-07-30)\n")
    assert got == "approved"


def test_unknown_status_is_not_silently_accepted():
    assert strand.declared_status("# X\n\nStatus: vibes\n") == "vibes"
    assert "vibes" not in strand.STATUS_VOCAB


def test_missing_status_returns_none():
    assert strand.declared_status("# X\n\nno status anywhere here\n") is None


def test_index_alone_does_not_count_as_a_consumer(tmp_path):
    """The rule is vacuous if the catalogue counts as a reader."""
    (tmp_path / "docs/analysis").mkdir(parents=True)
    (tmp_path / "docs/analysis/lonely.md").write_text("# Lonely\n", encoding="utf8")
    (tmp_path / "docs/INDEX.md").write_text("- [analysis/lonely.md](analysis/lonely.md)\n",
                                            encoding="utf8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert any("lonely.md" in p and "nothing outside" in p for p in probs)


def test_repo_is_clean():
    """The real repository passes both rules today."""
    r = subprocess.run([sys.executable, str(REPO / "tools/docmap/strand.py"),
                        "check", "--project", str(REPO)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_atlas_selftest_passes():
    """atlas.py ships with a selftest and it must stay green.

    Added 2026-08-05: the tool was built with a selftest and wired to nothing, which is
    the same defect it exists to find. A selftest no runner invokes is a selftest that
    has never been observed to pass anywhere but the author's terminal.
    """
    r = subprocess.run([sys.executable, str(REPO / "tools/docmap/atlas.py"), "selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_adr_vocabulary_is_admitted():
    """`accepted` is Nygard's ADR vocabulary and every file in docs/adr/ uses it.

    Third time on 2026-08-05 that this oracle rejected a legitimate status form. The
    other two are pinned above. A vocabulary that rejects the corpus it governs is
    checking its own ruled shape, not the property (L-2026-07-31-b).
    """
    for status in ("accepted", "rejected", "deprecated"):
        assert status in strand.STATUS_VOCAB
    assert strand.declared_status("# X\n\nStatus: accepted\n") == "accepted"


def test_the_exemption_ledger_is_not_a_consumer(tmp_path):
    """Adding an exemption must not, by itself, clear the violation it excuses.

    Found 2026-08-05: `docs/strand-exempt.txt` lists the paths it exempts, so it counted
    as a REFERENCE to each of them. Ten documents flipped from stranded to "exempt but
    now referenced, remove the exemption" the moment they were exempted. A bookkeeping
    surface is never a consumer, which is the same argument the docstring already makes
    for docs/INDEX.md.
    """
    (tmp_path / "docs/analysis").mkdir(parents=True)
    (tmp_path / "docs/analysis/lonely.md").write_text("# Lonely\n", encoding="utf8")
    (tmp_path / "docs/strand-exempt.txt").write_text(
        "docs/analysis/lonely.md | held as evidence\n", encoding="utf8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert not any("Remove the exemption" in p for p in probs), probs
    assert not any("nothing outside" in p for p in probs), probs


def test_generated_inventories_are_not_consumers(tmp_path):
    """A generated map that lists every document made R2 vacuous.

    Found 2026-08-05. docs/DOCMAP.md carries 990 rows naming nearly every document, so
    almost nothing could ever be reported unreferenced. The "0 stranded" result reported
    on 2026-08-04 was an artefact of that, not a measurement.
    """
    (tmp_path / "docs/analysis").mkdir(parents=True)
    (tmp_path / "docs/analysis/lonely.md").write_text("# Lonely\n", encoding="utf8")
    (tmp_path / "docs/DOCMAP.md").write_text(
        "| `docs/analysis/lonely.md` | 2026-08-05 | current |\n", encoding="utf8")
    (tmp_path / "docs/CODEBASE-MAP.md").write_text("docs/analysis/lonely.md\n", encoding="utf8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert any("lonely.md" in p and "nothing outside" in p for p in probs), probs


def _init_tree(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)


def test_r3_fires_on_stray_root_markdown(tmp_path):
    """R3: a .md at the root that is not allowlisted fails the check.

    Measured 2026-11-07: nine doc files landed at the root between 2026-08-31
    and 2026-10-15, months after #92 filed the same complaint, because nothing
    failed when they landed.
    """
    (tmp_path / "stray-note.md").write_text("# Stray\n", encoding="utf8")
    _init_tree(tmp_path)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert any("stray-note.md" in p and "R3 allowlist" in p for p in probs), probs


def test_r3_fires_on_extensionless_text(tmp_path):
    """R3: an extensionless text file at the root is a stray too.

    The case that proved the suffix-only form wrong: gem07-10, a Gemini research
    note with no suffix, sat at the root from 2026-10-08.
    """
    (tmp_path / "gem-note").write_text("a research note with no suffix\n", encoding="utf8")
    _init_tree(tmp_path)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert any("gem-note" in p and "R3 allowlist" in p for p in probs), probs


def test_r3_silent_on_allowlisted_and_config(tmp_path):
    """R3: canonical entry points, LICENSE, dotfiles and binaries stay silent."""
    (tmp_path / "TODO.md").write_text("# Roadmap\n", encoding="utf8")
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf8")
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf8")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0not text")
    _init_tree(tmp_path)
    probs = strand.problems(strand.evaluate(tmp_path))
    assert not any("R3 allowlist" in p for p in probs), probs
