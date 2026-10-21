#!/usr/bin/env python3
"""CI gate for the docs RAG index (claude-setup#422).

Fails closed when:
  1. a corpus doc (docs/specs/2026-*-corpus-*.md) is not linked from docs/RAG.md
     (this is what keeps the strand gate R2 green: RAG.md is the consumer
     surface that is actually read);
  2. a corpus doc is missing from tools/docs-rag/manifest.json (the checked-in
     proof that ingest.py indexed it);
  3. manifest.json disagrees with the ingest contract (collection, embedder,
     dim).

Stdlib only — safe to run in CI with no credentials and no network.

Usage:
  python tools/docs-rag/check_index.py check     # exit 1 on any violation
  python tools/docs-rag/check_index.py selftest  # prove the check can go red
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

CORPUS_GLOB = "docs/specs/2026-*-corpus-*.md"
RAG_MD = "docs/RAG.md"
MANIFEST = "tools/docs-rag/manifest.json"
EXPECTED = {"collection": "docs_rag_v1",
            "embedder": "nvidia/nemotron-3-embed-1b",
            "dim": 2048}


def corpus_docs(repo: Path) -> list[Path]:
    return sorted(repo.glob(CORPUS_GLOB))


def check(repo: Path) -> list[str]:
    """Return a list of violation strings; empty means green."""
    violations = []
    docs = corpus_docs(repo)
    if not docs:
        return ["no corpus docs found under docs/specs/ — glob broken?"]
    rag = repo / RAG_MD
    if not rag.exists():
        return [f"{RAG_MD} missing: the RAG surface page must exist"]
    rag_text = rag.read_text(encoding="utf-8", errors="ignore")
    man_path = repo / MANIFEST
    if not man_path.exists():
        violations.append(f"{MANIFEST} missing: run tools/docs-rag/ingest.py")
        manifest_docs = {}
    else:
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return [f"{MANIFEST} is not valid JSON: {e}"]
        for key, want in EXPECTED.items():
            if manifest.get(key) != want:
                violations.append(
                    f"{MANIFEST}: {key}={manifest.get(key)!r}, "
                    f"expected {want!r}")
        manifest_docs = manifest.get("docs", {})
    for p in docs:
        rel = p.relative_to(repo).as_posix()
        base = p.name
        stem = p.stem
        # strand.py counts a reference when basename, path or stem appears;
        # the CI gate mirrors that so the two can never disagree silently.
        if not (base in rag_text or rel in rag_text or stem in rag_text):
            violations.append(f"{rel} not linked from {RAG_MD}")
        entry = manifest_docs.get(stem)
        if not entry:
            violations.append(f"{rel} missing from {MANIFEST}")
        elif entry.get("n_chunks", 0) < 1:
            violations.append(f"{rel} has zero chunks in {MANIFEST}")
    return violations


def selftest() -> None:
    """Prove every rule above can fire, on a temp fixture."""
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "docs" / "specs").mkdir(parents=True)
        (repo / "tools" / "docs-rag").mkdir(parents=True)
        doc = repo / "docs" / "specs" / "2026-08-31-corpus-demo.md"
        doc.write_text("# Demo\n\n**Status:** done\n")
        # 1. missing RAG.md
        v = check(repo)
        assert any("RAG.md" in x and "missing" in x for x in v), v
        # 2. doc not linked
        (repo / "docs" / "RAG.md").write_text("# RAG\n\nNo links here.\n")
        v = check(repo)
        assert any("not linked" in x for x in v), v
        assert any("manifest" in x.lower() for x in v), v
        # 3. linked but not in manifest
        (repo / "docs" / "RAG.md").write_text(
            "# RAG\n\n- [demo](specs/2026-08-31-corpus-demo.md)\n")
        v = check(repo)
        assert any("missing from" in x for x in v), v
        # 4. manifest with wrong contract
        (repo / "tools" / "docs-rag" / "manifest.json").write_text(
            json.dumps({"collection": "wrong", "embedder": "x", "dim": 1,
                        "docs": {"2026-08-31-corpus-demo":
                                 {"n_chunks": 2, "chunk_ids": ["a", "b"]}}}))
        v = check(repo)
        assert any("collection='wrong'" in x for x in v), v
        # 5. green path
        (repo / "tools" / "docs-rag" / "manifest.json").write_text(
            json.dumps({"collection": "docs_rag_v1",
                        "embedder": "nvidia/nemotron-3-embed-1b",
                        "dim": 2048,
                        "docs": {"2026-08-31-corpus-demo":
                                 {"n_chunks": 2, "chunk_ids": ["a", "b"]}}}))
        v = check(repo)
        assert v == [], v
    print("check_index selftest: all 5 cases behave as specified")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "selftest":
        selftest()
    elif cmd == "check":
        repo = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        violations = check(repo)
        if violations:
            print("DOCS-RAG INDEX CHECK: FAIL")
            for v in violations:
                print("  -", v)
            sys.exit(1)
        print(f"DOCS-RAG INDEX CHECK: green "
              f"({len(corpus_docs(repo))} corpus docs linked + indexed)")
    else:
        sys.exit(f"unknown command {cmd!r}")
