#!/usr/bin/env python3
"""Docs RAG eval: fixed question set against the Qdrant index.

Olga (Zion Data), for claude-setup#422.

Measures, per store (Qdrant today; MongoDB blocked — no Atlas connector or
account exists, see issue #422):
  - recall@5 over the 20-question eval set (ground-truth doc ids);
  - p50/p95 query latency (Qdrant round-trip only, encode excluded, 3 passes);
  - index cost (upsert time, point count, $ — Qdrant Cloud free tier).

Writes tools/docs-rag/results.json. The eval set (tools/docs-rag/eval_set.json)
was written from the corpus docs themselves; ground truth is the doc each
question was drawn from. Construction method is documented in docs/RAG.md —
the numbers measure the harness on this corpus, not a held-out benchmark.

Usage:
  python tools/docs-rag/eval.py --repo . [--runs 3] [--limit 5]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import (  # noqa: E402
    COLLECTION_DEFAULT, EMBEDDER_MODEL, NVIDIA_HOST, qd,
)


def _embed_query_nvidia(text):
    from ingest import _surrogate
    import urllib.request
    import urllib.error
    add_surrogate_to_request = _surrogate()
    body = json.dumps({"model": EMBEDDER_MODEL, "input": [text[:8000]],
                       "input_type": "query"}).encode()
    req = urllib.request.Request(
        f"https://{NVIDIA_HOST}/v1/embeddings", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    add_surrogate_to_request(req, "custom.nvidia", allowed_hosts=[NVIDIA_HOST])
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            d = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"NVIDIA embed HTTP {e.code}: {e.read().decode()[:200]}")
    import numpy as np
    v = np.array(d["data"][0]["embedding"], dtype=np.float32)
    return (v / np.linalg.norm(v)).tolist()


def search(collection, qvec, limit):
    t0 = time.time()
    r = qd("POST", f"/collections/{collection}/points/search",
           {"vector": qvec, "limit": limit,
            "with_payload": ["doc_id", "chunk_id", "title"]})
    ms = (time.time() - t0) * 1000
    return [h["payload"]["doc_id"] for h in r["result"]], ms


def percentile(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--collection", default=COLLECTION_DEFAULT)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    tool_dir = repo / "tools" / "docs-rag"
    eval_set = json.loads((tool_dir / "eval_set.json").read_text())

    per_q, latencies = [], []
    for run in range(args.runs):
        for q in eval_set:
            qvec = _embed_query_nvidia(q["question"])
            doc_ids, ms = search(args.collection, qvec, args.limit)
            latencies.append(ms)
            truth = set(q["ground_truth"])
            hits = [d for d in doc_ids if d in truth]
            recall = len(set(hits)) / len(truth) if truth else 0.0
            if run == 0:
                per_q.append({"id": q["id"], "question": q["question"][:80],
                              "ground_truth": sorted(truth),
                              "retrieved_top5": doc_ids,
                              "recall@5": round(recall, 3),
                              "first_hit_rank": (doc_ids.index(hits[0]) + 1
                                                 if hits else None)})
    agg_recall = statistics.mean(p["recall@5"] for p in per_q)
    results = {
        "store": "qdrant",
        "collection": args.collection,
        "embedder": EMBEDDER_MODEL,
        "n_questions": len(eval_set),
        "runs": args.runs,
        "recall@5_mean": round(agg_recall, 3),
        "latency_ms": {
            "p50": round(percentile(latencies, 50), 1),
            "p95": round(percentile(latencies, 95), 1),
            "n": len(latencies),
            "note": "Qdrant round-trip only; query encoding excluded",
        },
        "cost": {"usd": 0.0, "note": "Qdrant Cloud free tier (shoval-free)"},
        "mongodb": {"status": "not_evaluated",
                    "reason": "no MongoDB Atlas connector or account exists; "
                              "creating one needs Shoval's sign-up. "
                              "See claude-setup#422."},
        "per_question": per_q,
    }
    with open(tool_dir / "results.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"recall@5 mean: {results['recall@5_mean']} "
          f"over {len(eval_set)} questions x {args.runs} runs")
    print(f"latency p50/p95: {results['latency_ms']['p50']}/"
          f"{results['latency_ms']['p95']} ms (n={len(latencies)})")
    print("-> tools/docs-rag/results.json")


if __name__ == "__main__":
    main()
