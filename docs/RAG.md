# Docs RAG: the corpus index

**Status:** living

This page is the read surface for the machine-generated corpus run-reports
under `docs/specs/` (claude-setup#422). Every report below is indexed in the
`docs_rag_v1` Qdrant collection and linked here, which keeps the
`strand.py` reachability gate (R2) green: this page is the consumer that
is actually read, not a catalogue entry.

## The index

- **Store:** Qdrant Cloud (cluster `shoval-free`, collection `docs_rag_v1`)
- **Embedder:** `nvidia/nemotron-3-embed-1b`, 2048 dims, L2-normalised, cosine distance
- **Chunking:** deterministic heading-based (`tools/docs-rag/ingest.py::chunk_doc`);
  sections split on `##` headings, long sections sub-split on paragraph
  boundaries, max 1500 chars per chunk, every chunk carries its doc title.
- **Rebuild:** `python tools/docs-rag/ingest.py --repo .`
  (needs the data-office connector environment for live Qdrant/NVIDIA calls;
  `--dry-run` exercises everything but the network)
- **Query:** `python tools/docs-rag/eval.py --repo .` runs the fixed 20-question
  eval set (`tools/docs-rag/eval_set.json`) and writes `tools/docs-rag/results.json`.
- **CI gate:** `python tools/docs-rag/check_index.py check` fails closed if any
  corpus doc is unlinked here or missing from `tools/docs-rag/manifest.json`.
  Wired into the ship-gate workflow next to the `strand.py check` step.

## Eval summary (2026-10-13)

| metric | Qdrant (`docs_rag_v1`) | MongoDB Atlas |
|---|---|---|
| recall@5 (20 questions x 3 runs) | **1.000** | not evaluated |
| first-hit rank | 1 for all 20 questions | — |
| query latency p50 | 852.5 ms | — |
| query latency p95 | 1192.9 ms (n=60) | — |
| index build | 1619 chunks, 197.4 s embed + upsert | — |
| cost | $0 (Cloud free tier `shoval-free`) | — |

The 20 questions were written from the corpus docs themselves (one question
per report, ground truth = the report it was drawn from). Construction method
is in `tools/docs-rag/eval.py`'s docstring. The numbers measure this harness on
this corpus; they are not a held-out benchmark.

## Store verdict

**Qdrant** (measured). **MongoDB Atlas was not evaluated**: no MongoDB connector
exists in `~/workspace/connected-tools.md` and no Atlas account is provisioned;
creating one needs Shoval's sign-up, which no agent can do. The comparison stays
open until credentials exist (Secure Vault path, never keys in the repo).
Qdrant is the docs-RAG store by default: it is the only measured option, it is
already live, and the eval above runs against it.

<details><summary><strong>2026-08-30</strong> — 40 reports</summary>

- [artifact extraction](specs/2026-08-30-corpus-artifact-extraction.md)
- [batch export](specs/2026-08-30-corpus-batch-export.md)
- [cache2action](specs/2026-08-30-corpus-cache2action.md)
- [chunk versions](specs/2026-08-30-corpus-chunk-versions.md)
- [chunker](specs/2026-08-30-corpus-chunker.md)
- [cite gate](specs/2026-08-30-corpus-cite-gate.md)
- [cluster store](specs/2026-08-30-corpus-cluster-store.md)
- [cluster](specs/2026-08-30-corpus-cluster.md)
- [contradiction detection](specs/2026-08-30-corpus-contradiction-detection.md)
- [coverage](specs/2026-08-30-corpus-coverage.md)
- [dedup](specs/2026-08-30-corpus-dedup.md)
- [diff](specs/2026-08-30-corpus-diff.md)
- [domain store](specs/2026-08-30-corpus-domain-store.md)
- [embedding rerank](specs/2026-08-30-corpus-embedding-rerank.md)
- [enrich](specs/2026-08-30-corpus-enrich.md)
- [export](specs/2026-08-30-corpus-export.md)
- [gaps](specs/2026-08-30-corpus-gaps.md)
- [health oracle](specs/2026-08-30-corpus-health-oracle.md)
- [license gate](specs/2026-08-30-corpus-license-gate.md)
- [lineage](specs/2026-08-30-corpus-lineage.md)
- [normalise](specs/2026-08-30-corpus-normalise.md)
- [outlier store](specs/2026-08-30-corpus-outlier-store.md)
- [paper rule](specs/2026-08-30-corpus-paper-rule.md)
- [pipeline](specs/2026-08-30-corpus-pipeline.md)
- [promote](specs/2026-08-30-corpus-promote.md)
- [quality trend](specs/2026-08-30-corpus-quality-trend.md)
- [quality](specs/2026-08-30-corpus-quality.md)
- [reclassify](specs/2026-08-30-corpus-reclassify.md)
- [row reuse](specs/2026-08-30-corpus-row-reuse.md)
- [sample](specs/2026-08-30-corpus-sample.md)
- [search](specs/2026-08-30-corpus-search.md)
- [semantic dedup](specs/2026-08-30-corpus-semantic-dedup.md)
- [semantic](specs/2026-08-30-corpus-semantic.md)
- [similarity store](specs/2026-08-30-corpus-similarity-store.md)
- [staleness sweep](specs/2026-08-30-corpus-staleness-sweep.md)
- [summarize](specs/2026-08-30-corpus-summarize.md)
- [tag store](specs/2026-08-30-corpus-tag-store.md)
- [tagger](specs/2026-08-30-corpus-tagger.md)
- [unified retrieval](specs/2026-08-30-corpus-unified-retrieval.md)
- [validate](specs/2026-08-30-corpus-validate.md)

</details>

<details><summary><strong>2026-08-31</strong> — 169 reports</summary>

- [artifact adoption](specs/2026-08-31-corpus-artifact-adoption.md)
- [artifact citation provenance](specs/2026-08-31-corpus-artifact-citation-provenance.md)
- [artifact domain distribution](specs/2026-08-31-corpus-artifact-domain-distribution.md)
- [artifact edge profile](specs/2026-08-31-corpus-artifact-edge-profile.md)
- [artifact graph](specs/2026-08-31-corpus-artifact-graph.md)
- [artifact name analysis](specs/2026-08-31-corpus-artifact-name-analysis.md)
- [artifact tag profile](specs/2026-08-31-corpus-artifact-tag-profile.md)
- [artifact version analysis](specs/2026-08-31-corpus-artifact-version-analysis.md)
- [artifact version conflicts](specs/2026-08-31-corpus-artifact-version-conflicts.md)
- [audit](specs/2026-08-31-corpus-audit.md)
- [chunk connectivity profile](specs/2026-08-31-corpus-chunk-connectivity-profile.md)
- [chunk evolution](specs/2026-08-31-corpus-chunk-evolution.md)
- [chunk kind profile](specs/2026-08-31-corpus-chunk-kind-profile.md)
- [chunk position analysis](specs/2026-08-31-corpus-chunk-position-analysis.md)
- [chunk profile](specs/2026-08-31-corpus-chunk-profile.md)
- [chunk similarity clusters](specs/2026-08-31-corpus-chunk-similarity-clusters.md)
- [citation age](specs/2026-08-31-corpus-citation-age.md)
- [citation analysis](specs/2026-08-31-corpus-citation-analysis.md)
- [citation edge profile](specs/2026-08-31-corpus-citation-edge-profile.md)
- [citation graph](specs/2026-08-31-corpus-citation-graph.md)
- [citation locator analysis](specs/2026-08-31-corpus-citation-locator-analysis.md)
- [citation tag profile](specs/2026-08-31-corpus-citation-tag-profile.md)
- [citation verification](specs/2026-08-31-corpus-citation-verification.md)
- [claim consensus](specs/2026-08-31-corpus-claim-consensus.md)
- [claim network](specs/2026-08-31-corpus-claim-network.md)
- [classification timeline](specs/2026-08-31-corpus-classification-timeline.md)
- [cross kind analysis](specs/2026-08-31-corpus-cross-kind-analysis.md)
- [cross ref density](specs/2026-08-31-corpus-cross-ref-density.md)
- [cross table outlier detector](specs/2026-08-31-corpus-cross-table-outlier-detector.md)
- [dashboard](specs/2026-08-31-corpus-dashboard.md)
- [diversity](specs/2026-08-31-corpus-diversity.md)
- [domain analysis](specs/2026-08-31-corpus-domain-analysis.md)
- [domain balance](specs/2026-08-31-corpus-domain-balance.md)
- [domain citation profile](specs/2026-08-31-corpus-domain-citation-profile.md)
- [domain edge depth](specs/2026-08-31-corpus-domain-edge-depth.md)
- [domain edge profile](specs/2026-08-31-corpus-domain-edge-profile.md)
- [domain score distribution](specs/2026-08-31-corpus-domain-score-distribution.md)
- [domain tag affinity](specs/2026-08-31-corpus-domain-tag-affinity.md)
- [edge basis analysis](specs/2026-08-31-corpus-edge-basis-analysis.md)
- [edge bridge analysis](specs/2026-08-31-corpus-edge-bridge-analysis.md)
- [edge chain analysis](specs/2026-08-31-corpus-edge-chain-analysis.md)
- [edge citation quality](specs/2026-08-31-corpus-edge-citation-quality.md)
- [edge confidence profile](specs/2026-08-31-corpus-edge-confidence-profile.md)
- [edge confidence](specs/2026-08-31-corpus-edge-confidence.md)
- [edge cycle detection](specs/2026-08-31-corpus-edge-cycle-detection.md)
- [edge density](specs/2026-08-31-corpus-edge-density.md)
- [edge detection timeline](specs/2026-08-31-corpus-edge-detection-timeline.md)
- [edge reachability](specs/2026-08-31-corpus-edge-reachability.md)
- [edge reciprocity analysis](specs/2026-08-31-corpus-edge-reciprocity-analysis.md)
- [edge resolution](specs/2026-08-31-corpus-edge-resolution.md)
- [edge source temporal lag](specs/2026-08-31-corpus-edge-source-temporal-lag.md)
- [edge text correlation](specs/2026-08-31-corpus-edge-text-correlation.md)
- [edge type transition](specs/2026-08-31-corpus-edge-type-transition.md)
- [enrichment lag profile](specs/2026-08-31-corpus-enrichment-lag-profile.md)
- [evidence chain audit](specs/2026-08-31-corpus-evidence-chain-audit.md)
- [evidence coverage](specs/2026-08-31-corpus-evidence-coverage.md)
- [freshness scorer](specs/2026-08-31-corpus-freshness-scorer.md)
- [fts citation reachability](specs/2026-08-31-corpus-fts-citation-reachability.md)
- [fts edge reachability](specs/2026-08-31-corpus-fts-edge-reachability.md)
- [heading citation correlation](specs/2026-08-31-corpus-heading-citation-correlation.md)
- [heading citation profile](specs/2026-08-31-corpus-heading-citation-profile.md)
- [heading depth analysis](specs/2026-08-31-corpus-heading-depth-analysis.md)
- [heading domain correlation](specs/2026-08-31-corpus-heading-domain-correlation.md)
- [heading domain profile](specs/2026-08-31-corpus-heading-domain-profile.md)
- [heading edge correlation](specs/2026-08-31-corpus-heading-edge-correlation.md)
- [heading edge profile](specs/2026-08-31-corpus-heading-edge-profile.md)
- [heading kind profile](specs/2026-08-31-corpus-heading-kind-profile.md)
- [heading license profile](specs/2026-08-31-corpus-heading-license-profile.md)
- [heading liveness profile](specs/2026-08-31-corpus-heading-liveness-profile.md)
- [heading publisher profile](specs/2026-08-31-corpus-heading-publisher-profile.md)
- [heading simhash profile](specs/2026-08-31-corpus-heading-simhash-profile.md)
- [heading status profile](specs/2026-08-31-corpus-heading-status-profile.md)
- [heading tag correlation](specs/2026-08-31-corpus-heading-tag-correlation.md)
- [heading tag profile](specs/2026-08-31-corpus-heading-tag-profile.md)
- [health scorecard](specs/2026-08-31-corpus-health-scorecard.md)
- [ingestion regression](specs/2026-08-31-corpus-ingestion-regression.md)
- [kind citation profile](specs/2026-08-31-corpus-kind-citation-profile.md)
- [kind domain profile](specs/2026-08-31-corpus-kind-domain-profile.md)
- [kind edge profile](specs/2026-08-31-corpus-kind-edge-profile.md)
- [kind liveness profile](specs/2026-08-31-corpus-kind-liveness-profile.md)
- [kind status profile](specs/2026-08-31-corpus-kind-status-profile.md)
- [kind tag profile](specs/2026-08-31-corpus-kind-tag-profile.md)
- [language distribution](specs/2026-08-31-corpus-language-distribution.md)
- [license citation profile](specs/2026-08-31-corpus-license-citation-profile.md)
- [license domain profile](specs/2026-08-31-corpus-license-domain-profile.md)
- [license edge analysis](specs/2026-08-31-corpus-license-edge-analysis.md)
- [license edge profile](specs/2026-08-31-corpus-license-edge-profile.md)
- [license kind profile](specs/2026-08-31-corpus-license-kind-profile.md)
- [license liveness profile](specs/2026-08-31-corpus-license-liveness-profile.md)
- [license status profile](specs/2026-08-31-corpus-license-status-profile.md)
- [license tag profile](specs/2026-08-31-corpus-license-tag-profile.md)
- [liveness citation profile](specs/2026-08-31-corpus-liveness-citation-profile.md)
- [liveness cross analysis](specs/2026-08-31-corpus-liveness-cross-analysis.md)
- [liveness domain profile](specs/2026-08-31-corpus-liveness-domain-profile.md)
- [liveness edge profile](specs/2026-08-31-corpus-liveness-edge-profile.md)
- [liveness status profile](specs/2026-08-31-corpus-liveness-status-profile.md)
- [liveness tag profile](specs/2026-08-31-corpus-liveness-tag-profile.md)
- [publisher citation profile](specs/2026-08-31-corpus-publisher-citation-profile.md)
- [publisher domain profile](specs/2026-08-31-corpus-publisher-domain-profile.md)
- [publisher edge profile](specs/2026-08-31-corpus-publisher-edge-profile.md)
- [publisher kind profile](specs/2026-08-31-corpus-publisher-kind-profile.md)
- [publisher license distribution](specs/2026-08-31-corpus-publisher-license-distribution.md)
- [publisher license profile](specs/2026-08-31-corpus-publisher-license-profile.md)
- [publisher liveness profile](specs/2026-08-31-corpus-publisher-liveness-profile.md)
- [publisher status profile](specs/2026-08-31-corpus-publisher-status-profile.md)
- [publisher tag profile](specs/2026-08-31-corpus-publisher-tag-profile.md)
- [query coverage](specs/2026-08-31-corpus-query-coverage.md)
- [readability](specs/2026-08-31-corpus-readability.md)
- [recommend](specs/2026-08-31-corpus-recommend.md)
- [simhash citation profile](specs/2026-08-31-corpus-simhash-citation-profile.md)
- [simhash distribution](specs/2026-08-31-corpus-simhash-distribution.md)
- [simhash domain profile](specs/2026-08-31-corpus-simhash-domain-profile.md)
- [simhash edge profile](specs/2026-08-31-corpus-simhash-edge-profile.md)
- [simhash kind profile](specs/2026-08-31-corpus-simhash-kind-profile.md)
- [simhash license profile](specs/2026-08-31-corpus-simhash-license-profile.md)
- [simhash liveness profile](specs/2026-08-31-corpus-simhash-liveness-profile.md)
- [simhash publisher profile](specs/2026-08-31-corpus-simhash-publisher-profile.md)
- [simhash status profile](specs/2026-08-31-corpus-simhash-status-profile.md)
- [simhash tag profile](specs/2026-08-31-corpus-simhash-tag-profile.md)
- [similarity analysis](specs/2026-08-31-corpus-similarity-analysis.md)
- [source argumentation balance](specs/2026-08-31-corpus-source-argumentation-balance.md)
- [source chain](specs/2026-08-31-corpus-source-chain.md)
- [source citation net](specs/2026-08-31-corpus-source-citation-net.md)
- [source composite profile](specs/2026-08-31-corpus-source-composite-profile.md)
- [source edge stance](specs/2026-08-31-corpus-source-edge-stance.md)
- [source enrichment completeness](specs/2026-08-31-corpus-source-enrichment-completeness.md)
- [source impact](specs/2026-08-31-corpus-source-impact.md)
- [source lifecycle](specs/2026-08-31-corpus-source-lifecycle.md)
- [source overlap analysis](specs/2026-08-31-corpus-source-overlap-analysis.md)
- [source overlap](specs/2026-08-31-corpus-source-overlap.md)
- [source provenance](specs/2026-08-31-corpus-source-provenance.md)
- [source size distribution](specs/2026-08-31-corpus-source-size-distribution.md)
- [status citation profile](specs/2026-08-31-corpus-status-citation-profile.md)
- [status domain profile](specs/2026-08-31-corpus-status-domain-profile.md)
- [status edge profile](specs/2026-08-31-corpus-status-edge-profile.md)
- [status enrichment profile](specs/2026-08-31-corpus-status-enrichment-profile.md)
- [status reason trends](specs/2026-08-31-corpus-status-reason-trends.md)
- [status tag profile](specs/2026-08-31-corpus-status-tag-profile.md)
- [supersession analysis](specs/2026-08-31-corpus-supersession-analysis.md)
- [supersession edge orphans](specs/2026-08-31-corpus-supersession-edge-orphans.md)
- [tag citation correlation](specs/2026-08-31-corpus-tag-citation-correlation.md)
- [tag citation yield](specs/2026-08-31-corpus-tag-citation-yield.md)
- [tag cooccurrence](specs/2026-08-31-corpus-tag-cooccurrence.md)
- [tag domain correlation](specs/2026-08-31-corpus-tag-domain-correlation.md)
- [tag domain profile](specs/2026-08-31-corpus-tag-domain-profile.md)
- [tag edge correlation](specs/2026-08-31-corpus-tag-edge-correlation.md)
- [tag edge profile](specs/2026-08-31-corpus-tag-edge-profile.md)
- [tag entropy](specs/2026-08-31-corpus-tag-entropy.md)
- [tag landscape](specs/2026-08-31-corpus-tag-landscape.md)
- [tag score trends](specs/2026-08-31-corpus-tag-score-trends.md)
- [tag verification breakdown](specs/2026-08-31-corpus-tag-verification-breakdown.md)
- [temporal distribution](specs/2026-08-31-corpus-temporal-distribution.md)
- [timeline](specs/2026-08-31-corpus-timeline.md)
- [topic coherence](specs/2026-08-31-corpus-topic-coherence.md)
- [topic model](specs/2026-08-31-corpus-topic-model.md)
- [upstream provenance](specs/2026-08-31-corpus-upstream-provenance.md)
- [verification timeline](specs/2026-08-31-corpus-verification-timeline.md)
- [version churn](specs/2026-08-31-corpus-version-churn.md)
- [version citation drift](specs/2026-08-31-corpus-version-citation-drift.md)
- [version claim edge cascade](specs/2026-08-31-corpus-version-claim-edge-cascade.md)
- [version domain stability](specs/2026-08-31-corpus-version-domain-stability.md)
- [version edge impact](specs/2026-08-31-corpus-version-edge-impact.md)
- [version fts coverage](specs/2026-08-31-corpus-version-fts-coverage.md)
- [version source profile](specs/2026-08-31-corpus-version-source-profile.md)
- [version tag stability](specs/2026-08-31-corpus-version-tag-stability.md)
- [version timeline](specs/2026-08-31-corpus-version-timeline.md)
- [vocab analysis](specs/2026-08-31-corpus-vocab-analysis.md)
- [word count distribution](specs/2026-08-31-corpus-word-count-distribution.md)
- [xray](specs/2026-08-31-corpus-xray.md)

</details>

<details><summary><strong>other</strong> — 1 reports</summary>

- [2026 07 31 research corpus and cache](specs/2026-07-31-research-corpus-and-cache.md)

</details>
