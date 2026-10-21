#!/usr/bin/env python3
"""Docs RAG ingest: corpus docs -> deterministic chunks -> embeddings -> Qdrant.

Olga (Zion Data), for claude-setup#422.

Pipeline (all deterministic; the store is the only variable):
  corpus docs (docs/specs/2026-*-corpus-*.md)
    -> chunk_doc()          deterministic heading-based chunking
    -> embed via NVIDIA nemotron-3-embed-1b (2048d), L2-normalised
    -> upsert into Qdrant collection docs_rag_v1
    -> tools/docs-rag/manifest.json  (checked in; CI reads this, not Qdrant)

Live Qdrant/NVIDIA calls need the connector surrogate mechanism
(/opt/hatch/skills/skill-creator/bin/dynamic_credentials), which only
exists on the agent VM. --dry-run builds chunks + manifest with fake
vectors so CI, tests and pstack can exercise everything but the network.

Usage:
  python tools/docs-rag/ingest.py --repo . [--collection docs_rag_v1]
  python tools/docs-rag/ingest.py --repo . --dry-run
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

EMBEDDER_MODEL = "nvidia/nemotron-3-embed-1b"
EMBEDDER_DIM = 2048
COLLECTION_DEFAULT = "docs_rag_v1"
QDRANT_HOST = "7e08b95f-91a1-44d3-b284-2d83c7c184c0.eu-west-2-0.aws.cloud.qdrant.io"
NVIDIA_HOST = "integrate.api.nvidia.com"

CORPUS_GLOB = "docs/specs/2026-*-corpus-*.md"
CHUNK_MAX_CHARS = 1500


# ---------------- corpus ----------------

def iter_corpus_docs(repo_root: Path):
    """Yield (doc_id, rel_path, text) for every corpus doc, sorted by path."""
    docs = sorted(repo_root.glob(CORPUS_GLOB))
    for p in docs:
        rel = p.relative_to(repo_root).as_posix()
        yield p.stem, rel, p.read_text(encoding="utf-8", errors="ignore")


# ---------------- chunking (deterministic) ----------------

HEADING = re.compile(r"^##\s+(.+)$", re.M)


def chunk_doc(doc_id: str, text: str, max_chars: int = CHUNK_MAX_CHARS):
    """Split a doc into deterministic chunks.

    Contract (pinned by tests):
    - same (doc_id, text) -> identical chunk list, every time;
    - chunk ids are f"{doc_id}#c{i:03d}", zero-padded, in document order;
    - every chunk carries the doc title as context prefix;
    - no chunk exceeds max_chars; splits happen on paragraph boundaries,
      falling back to hard cuts only when a paragraph itself is too long.
    """
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else doc_id
    # split into sections on ## headings; preamble (before first ##) is section 0
    parts = HEADING.split(text)
    sections = []
    if parts[0].strip():
        sections.append(("", parts[0]))
    for i in range(1, len(parts), 2):
        head = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((head, body))
    chunks = []
    for head, body in sections:
        ctx = f"[{title}" + (f" / {head}]" if head else "]")
        for piece in _split_paragraphs(body, max_chars - len(ctx) - 1):
            chunks.append(f"{ctx}\n{piece.strip()}")
    # drop empties but keep order; reindex
    chunks = [c for c in chunks if c.strip()]
    return [{"chunk_id": f"{doc_id}#c{i:03d}", "doc_id": doc_id,
             "title": title, "text": c}
            for i, c in enumerate(chunks)]


def _split_paragraphs(body: str, budget: int):
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return []
    out, cur = [], ""
    for p in paras:
        p = p.strip()
        while len(p) > budget:
            # hard cut only for pathological single paragraphs
            if cur:
                out.append(cur)
                cur = ""
            out.append(p[:budget])
            p = p[budget:]
        if len(cur) + 1 + len(p) <= budget:
            cur = (cur + "\n\n" + p).strip() if cur else p
        else:
            if cur:
                out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return out


# ---------------- embeddings ----------------

def _surrogate():
    sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
    from dynamic_credentials import add_surrogate_to_request
    return add_surrogate_to_request


def embed_texts_nvidia(texts):
    """Embed via NVIDIA NIM nemotron-3-embed-1b. Returns L2-normalised vectors."""
    import numpy as np
    add_surrogate_to_request = _surrogate()
    out = []
    for s in range(0, len(texts), 20):
        body = json.dumps({"model": EMBEDDER_MODEL,
                           "input": [t[:8000] for t in texts[s:s + 20]],
                           "input_type": "passage"}).encode()
        req = urllib.request.Request(
            f"https://{NVIDIA_HOST}/v1/embeddings", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        add_surrogate_to_request(req, "custom.nvidia", allowed_hosts=[NVIDIA_HOST])
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"NVIDIA embed HTTP {e.code}: {e.read().decode()[:200]}")
        items = sorted(d["data"], key=lambda x: x["index"])
        out.extend([it["embedding"] for it in items])
        time.sleep(1)
    emb = np.array(out, dtype=np.float32)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    return emb


def fake_vectors(n, dim=EMBEDDER_DIM):
    """Deterministic stand-in vectors for --dry-run / tests. NOT for eval."""
    import numpy as np
    rng = np.random.default_rng(422)
    v = rng.standard_normal((n, dim)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# ---------------- qdrant ----------------

def qd(method, path, body=None):
    add_surrogate_to_request = _surrogate()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"https://{QDRANT_HOST}" + path, data=data,
                                 method=method,
                                 headers={"Content-Type": "application/json"})
    add_surrogate_to_request(req, "custom.qdrant-data", allowed_hosts=[QDRANT_HOST])
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Qdrant {method} {path}: HTTP {e.code} "
                           f"{e.read().decode()[:300]}")


def upsert_collection(chunks, vectors, collection):
    try:
        qd("DELETE", f"/collections/{collection}")
    except RuntimeError:
        pass
    qd("PUT", f"/collections/{collection}",
       {"vectors": {"size": EMBEDDER_DIM, "distance": "Cosine"}})
    points = [{"id": i, "vector": vectors[i].tolist(),
               "payload": {"doc_id": c["doc_id"], "chunk_id": c["chunk_id"],
                           "title": c["title"], "text": c["text"][:600]}}
              for i, c in enumerate(chunks)]
    for s in range(0, len(points), 50):
        qd("PUT", f"/collections/{collection}/points",
           {"points": points[s:s + 50]})
    return qd("GET", f"/collections/{collection}")["result"]["points_count"]


# ---------------- manifest ----------------

def build_manifest(chunks, collection):
    by_doc = {}
    for c in chunks:
        d = by_doc.setdefault(c["doc_id"], {"n_chunks": 0, "chunk_ids": []})
        d["n_chunks"] += 1
        d["chunk_ids"].append(c["chunk_id"])
    return {"collection": collection,
            "embedder": EMBEDDER_MODEL,
            "dim": EMBEDDER_DIM,
            "n_chunks": len(chunks),
            "n_docs": len(by_doc),
            "docs": by_doc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="repo root")
    ap.add_argument("--collection", default=COLLECTION_DEFAULT)
    ap.add_argument("--dry-run", action="store_true",
                    help="no network: fake vectors, no Qdrant upsert")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    out_dir = repo / "tools" / "docs-rag"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = list(iter_corpus_docs(repo))
    print(f"corpus docs: {len(docs)}")
    chunks = []
    for doc_id, rel, text in docs:
        chunks.extend(chunk_doc(doc_id, text))
    print(f"chunks: {len(chunks)}")

    t0 = time.time()
    if args.dry_run:
        vectors = fake_vectors(len(chunks))
        count = len(chunks)
        print("dry-run: fake vectors, no upsert")
    else:
        vectors = embed_texts_nvidia([c["text"] for c in chunks])
        enc_s = time.time() - t0
        print(f"embedded in {enc_s:.1f}s")
        count = upsert_collection(chunks, vectors, args.collection)
        print(f"upserted {count} points into {args.collection}")

    manifest = build_manifest(chunks, args.collection)
    with open(out_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"manifest: {manifest['n_docs']} docs, {manifest['n_chunks']} chunks "
          f"-> tools/docs-rag/manifest.json")


if __name__ == "__main__":
    main()
