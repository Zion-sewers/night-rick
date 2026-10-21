# Docs Index: Claude OS

Every tracked prose document under `docs/`, grouped. One TODO, one INDEX
(docs-control-plane rule).

Coverage is the point. On 2026-07-31 this file listed 22 of 112 prose documents;
`docs/DOCMAP.md` had been printing that reachability number on every regeneration
with nothing failing on it. Measured in
`analysis/2026-07-31-inventory-reconciliation-and-the-docs-control-plane.md`.
A status shown as `not declared` is a real gap in that document, not a gap here:
`docmap.py` derives a class-based status when a document declares none, which
answers what kind of document it is and never whether it is still true.

Titles and declared statuses below were extracted from the files themselves rather
than written from memory; the spine section is hand-curated. There is no generator on
disk, which means this file WILL drift the next time a document lands. That is the
open ticket, not a promise made here: nothing currently fails when it drifts.

## Spine

- [PLAN-SPINE.md](PLAN-SPINE.md): the unified plan spine. One row per live surface: PRD -> spec(s) -> current slice -> next slice -> ticket -> % built, each cell VERIFIED or marked `unverified`. Written 2026-08-17 glue pass.
- [../CLAUDE-OS.md](../CLAUDE-OS.md): single source of truth. Layers L0 to L8, deep-work protocol, native-feature map, supersession table.
- [SESSION-BOOT.md](SESSION-BOOT.md): any fresh session, full context from disk in 60 seconds (ADR-0010).
- [charters.md](charters.md): the four session lanes A/B/C/D. Letters renumbered from B/C/D/E by ADR-0016 on 2026-07-30; pre-cutover ledger rows still say the old letter.
- [OPERATOR-RUNBOOK.md](OPERATOR-RUNBOOK.md): the manual steps only the operator can do.
- [EXECUTION-PLAN.md](EXECUTION-PLAN.md): P0 to P4 harness build phases.
- [SYSTEM-MAP.md](SYSTEM-MAP.md): the whole OS scored inv-versus-need. Created 2026-07-24; several rows marked VERIFIED there are now stale, corrected in the 2026-07-31 reconciliation.
- [QUALITY-CONTRACT.md](QUALITY-CONTRACT.md): why `quality-contract.json` says what it says, per domain.
- [taste.md](taste.md): the /diverge pick ledger, one row per decision with its reason.
- [ESTATE-DIRECTORY-CATALOG.md](ESTATE-DIRECTORY-CATALOG.md): directory and repository catalog for the estate.
- [dir-purpose.txt](dir-purpose.txt), [doc-status.txt](doc-status.txt): the two registries `codemap.py` and `docmap.py` read.
- [CODEBASE-MAP.md](CODEBASE-MAP.md), [DOCMAP.md](DOCMAP.md): GENERATED. A hand edit reads as drift and fails the gate.

## PRDs

- [analysis/2026-08-05-enforcement-topology-measured.md](analysis/2026-08-05-enforcement-topology-measured.md): Enforcement topology: global vs per-project vs document-only, measured *(status: measurement)*
- [analysis/2026-08-03-code-audit-analysis-sweep-and-research-provenance.md](analysis/2026-08-03-code-audit-analysis-sweep-and-research-provenance.md): Code audit, the 37-file analysis sweep, and where this session's research landed *(status: measurement)*
- [analysis/2026-08-05-implementation-reasoning-per-file.md](analysis/2026-08-05-implementation-reasoning-per-file.md): Why each source file is shaped the way it is, applying ADR-0021 per file *(status: analysis)*
- [analysis/2026-08-10-inbox-secret-exposure.md](analysis/2026-08-10-inbox-secret-exposure.md): A secret reached a pushed commit; why removing it from HEAD does not remove it, and the operator action that does *(status: active)*
- [specs/2026-08-03-detail-passes-teleology-and-creativity.md](specs/2026-08-03-detail-passes-teleology-and-creativity.md): Spec: dynamic detail passes, the teleological gap, and measured creativity *(status: DESIGN)*
- [specs/2026-08-30-blast-radius-gate.md](specs/2026-08-30-blast-radius-gate.md): Spec: blast-radius gate domain, transitive Python import graph for PR review fanout *(status: done)*
- [specs/2026-08-30-waiver-falsifier.md](specs/2026-08-30-waiver-falsifier.md): Spec: waiver-falsifier execution, dedicated verification commands for gate waivers *(status: done)*
- [specs/2026-08-30-rules-enforcement-gate.md](specs/2026-08-30-rules-enforcement-gate.md): Spec: rules-as-enforcement gate domain, mechanical predicates in rule frontmatter *(status: done)*
- [specs/2026-08-30-lane-enforcement-gate.md](specs/2026-08-30-lane-enforcement-gate.md): Spec: lane-enforcement gate domain, claims ledger lane validation *(status: done)*
- [specs/2026-08-30-todo-inbox-gate.md](specs/2026-08-30-todo-inbox-gate.md): Spec: todo-inbox gate domain, TODO.md prompt-inbox block vs intent store *(status: done)*
- [specs/2026-08-30-refute-gate.md](specs/2026-08-30-refute-gate.md): Spec: refute gate domain, claim falsifier enforcement *(status: done)*
- [specs/2026-08-30-bus-integrity-gate.md](specs/2026-08-30-bus-integrity-gate.md): Spec: bus-integrity gate domain, hash-chain verification of event bus ledger *(status: done)*
- [specs/2026-08-30-skilleval-gate.md](specs/2026-08-30-skilleval-gate.md): Spec: skilleval gate domain, skill routing quality enforcement *(status: done)*
- [specs/2026-08-30-branch-health-gate.md](specs/2026-08-30-branch-health-gate.md): Spec: branch_health gate domain, stale branches and orphaned worktrees *(status: done)*
- [specs/2026-08-30-skip-tracker-gate.md](specs/2026-08-30-skip-tracker-gate.md): Spec: skip_tracker gate domain, pytest skip count regression detection *(status: done)*
- [specs/2026-08-30-prose-fit-gate.md](specs/2026-08-30-prose-fit-gate.md): Spec: prose_fit gate domain, fitted prose-quality thresholds from score corpus *(status: done)*
- [specs/2026-08-30-lesson-check-gate.md](specs/2026-08-30-lesson-check-gate.md): Spec: lesson_check gate domain, lessons ledger structural integrity validation *(status: done)*
- [specs/2026-08-30-gate-health-gate.md](specs/2026-08-30-gate-health-gate.md): Spec: gate_health gate domain, gate-run ledger structural integrity validation *(status: done)*
- [specs/2026-08-30-corpus-contradiction-detection.md](specs/2026-08-30-corpus-contradiction-detection.md): Spec: corpus contradiction detection, three mechanical detectors for conflicting claims in the research corpus *(status: done)*
- [specs/2026-08-30-corpus-artifact-extraction.md](specs/2026-08-30-corpus-artifact-extraction.md): Spec: corpus artifact extraction, populates the artifacts table from chunk text with disk evidence *(status: done)*
- [specs/2026-08-30-corpus-row-reuse.md](specs/2026-08-30-corpus-row-reuse.md): Spec: corpus row-reuse write-back, derived source and chunk creation with one-hop provenance cap *(status: done)*
- [specs/2026-08-30-corpus-cache2action.md](specs/2026-08-30-corpus-cache2action.md): Spec: corpus cache-to-action proposal path, trust flags and evidence verification with no auto-execution *(status: done)*
- [specs/2026-08-30-corpus-embedding-rerank.md](specs/2026-08-30-corpus-embedding-rerank.md): Spec: corpus embedding and rerank, hashed char-ngram TF-IDF + PCA with generation-tracked cosine reranking *(status: done)*
- [specs/2026-08-30-corpus-license-gate.md](specs/2026-08-30-corpus-license-gate.md): Spec: corpus license gate, mechanical hostname blocking and license verdict enforcement at ingestion *(status: done)*
- [specs/2026-08-30-corpus-unified-retrieval.md](specs/2026-08-30-corpus-unified-retrieval.md): Spec: corpus unified retrieval, section 7.2 record shape with staleness, trust, contradictions, and artifacts *(status: done)*
- [specs/2026-08-30-corpus-health-oracle.md](specs/2026-08-30-corpus-health-oracle.md): Spec: corpus health oracle, aggregated defect queries and tool signals into a pass/fail verdict *(status: done)*
- [specs/2026-08-30-corpus-pipeline.md](specs/2026-08-30-corpus-pipeline.md): Spec: corpus ingestion pipeline, end-to-end orchestration of all stages with structured reporting *(status: done)*
- [specs/2026-08-30-corpus-staleness-sweep.md](specs/2026-08-30-corpus-staleness-sweep.md): Spec: corpus staleness sweep, proactive freshness check with DB updates for drifted local files *(status: done)*
- [specs/2026-08-30-corpus-export.md](specs/2026-08-30-corpus-export.md): Spec: corpus export, serializes corpus or filtered subsets to JSON/JSONL for external analysis *(status: done)*
- [specs/2026-08-30-corpus-search.md](specs/2026-08-30-corpus-search.md): Spec: corpus search, unified search across research corpus and books index with graceful degradation *(status: done)*
- [specs/2026-08-30-corpus-coverage.md](specs/2026-08-30-corpus-coverage.md): Spec: corpus coverage, reports indexed vs on-disk files with per-directory breakdown and books awareness *(status: done)*
- [specs/2026-08-30-corpus-diff.md](specs/2026-08-30-corpus-diff.md): Spec: corpus diff, timestamp-based change tracking with new sources, chunks, contradictions, and artifacts *(status: done)*
- [specs/2026-08-30-corpus-promote.md](specs/2026-08-30-corpus-promote.md): Spec: corpus promote, review and promote quarantined chunks to accepted with source-level bulk operations *(status: done)*
- [specs/2026-08-30-corpus-validate.md](specs/2026-08-30-corpus-validate.md): Spec: corpus validate, structural integrity checks for orphan rows, empty text, and referential consistency *(status: done)*
- [specs/2026-08-30-corpus-sample.md](specs/2026-08-30-corpus-sample.md): Spec: corpus sample, stratified random sampling for quality review with filtered draw and reproducible seeds *(status: done)*
- [specs/2026-08-30-corpus-cluster.md](specs/2026-08-30-corpus-cluster.md): Spec: corpus cluster, simhash similarity, shared citation, and source overlap clustering for topical analysis *(status: done)*
- [specs/2026-08-30-corpus-summarize.md](specs/2026-08-30-corpus-summarize.md): Spec: corpus summarize, comprehensive statistical profile with citation density, artifact adoption, and freshness *(status: done)*
- [specs/2026-08-30-corpus-lineage.md](specs/2026-08-30-corpus-lineage.md): Spec: corpus lineage, provenance chain tracing with recursive downstream traversal and orphan detection *(status: done)*
- [specs/2026-08-30-corpus-quality.md](specs/2026-08-30-corpus-quality.md): Spec: corpus quality scoring, weighted composite scores for chunk and source prioritisation *(status: done)*
- [specs/2026-08-30-corpus-quality-trend.md](specs/2026-08-30-corpus-quality-trend.md): Spec: quality trend tracker, aggregate snapshot history for temporal quality monitoring *(status: done)*
- [specs/2026-08-30-corpus-gaps.md](specs/2026-08-30-corpus-gaps.md): Spec: corpus gap analysis, reference domain coverage checks and uncovered directory detection *(status: done)*
- [specs/2026-08-30-corpus-reclassify.md](specs/2026-08-30-corpus-reclassify.md): Spec: corpus chunk reclassification, content heuristic kind detection and mismatch correction *(status: done)*
- [specs/2026-08-30-corpus-dedup.md](specs/2026-08-30-corpus-dedup.md): Spec: corpus deduplication, exact and near-duplicate detection with simhash hamming distance and claim_edges *(status: done)*
- [specs/2026-08-30-corpus-tagger.md](specs/2026-08-30-corpus-tagger.md): Spec: corpus auto-tagger, TF-IDF topic scoring across 20 domain vocabularies *(status: done)*
- [specs/2026-08-30-corpus-semantic.md](specs/2026-08-30-corpus-semantic.md): Spec: corpus semantic analysis, sklearn TF-IDF classification, similarity, clustering, and outlier detection *(status: done)*
- [specs/2026-08-31-corpus-topic-model.md](specs/2026-08-31-corpus-topic-model.md): Spec: corpus NMF topic model, unsupervised topic discovery via matrix factorization *(status: done)*
- [specs/2026-08-31-corpus-topic-coherence.md](specs/2026-08-31-corpus-topic-coherence.md): Spec: topic coherence scoring via NPMI with n_topics suggestion heuristic *(status: done)*
- [specs/2026-08-31-corpus-citation-graph.md](specs/2026-08-31-corpus-citation-graph.md): Spec: citation graph analysis over claim_edges with authority, hub, and isolation metrics *(status: done)*
- [specs/2026-08-31-corpus-vocab-analysis.md](specs/2026-08-31-corpus-vocab-analysis.md): Spec: corpus vocabulary profiling, distinctive terms per kind via TF-IDF, and domain coverage measurement *(status: done)*
- [specs/2026-08-31-corpus-xray.md](specs/2026-08-31-corpus-xray.md): Spec: cross-table analysis joining clusters, topics, similarities, and contradictions *(status: done)*
- [specs/2026-08-31-corpus-source-impact.md](specs/2026-08-31-corpus-source-impact.md): Spec: source impact scoring by downstream analytical footprint *(status: done)*
- [specs/2026-08-31-corpus-recommend.md](specs/2026-08-31-corpus-recommend.md): Spec: multi-signal chunk recommender fusing topic, cluster, similarity, tags, and edges *(status: done)*
- [specs/2026-08-31-corpus-diversity.md](specs/2026-08-31-corpus-diversity.md): Spec: corpus diversity analysis with Shannon entropy, Gini coefficient, and dominated-topic detection *(status: done)*
- [specs/2026-08-31-corpus-tag-cooccurrence.md](specs/2026-08-31-corpus-tag-cooccurrence.md): Spec: tag co-occurrence analysis with PMI ranking, community detection, and hub identification *(status: done)*
- [specs/2026-08-31-corpus-source-overlap.md](specs/2026-08-31-corpus-source-overlap.md): Spec: source overlap analysis measuring content redundancy between sources *(status: done)*
- [specs/2026-08-31-corpus-timeline.md](specs/2026-08-31-corpus-timeline.md): Spec: corpus timeline analysis with ingestion velocity, age distribution, and topic trends *(status: done)*
- [specs/2026-08-31-corpus-claim-network.md](specs/2026-08-31-corpus-claim-network.md): Spec: claim network analysis with connected components, bridge chunks, and contradiction clusters *(status: done)*
- [specs/2026-08-31-corpus-dashboard.md](specs/2026-08-31-corpus-dashboard.md): Spec: corpus dashboard aggregating chunk, source, edge, and signal coverage metrics *(status: done)*
- [specs/2026-08-31-corpus-chunk-profile.md](specs/2026-08-31-corpus-chunk-profile.md): Spec: chunk profile assembling complete dossier with provenance, edges, tags, topic, cluster, similarity, and citations *(status: done)*
- [specs/2026-08-31-corpus-audit.md](specs/2026-08-31-corpus-audit.md): Spec: corpus audit cross-referencing signals to detect intra-cluster contradictions, unverified citations, weak tags, orphans, and stale sources *(status: done)*
- [specs/2026-08-31-corpus-edge-resolution.md](specs/2026-08-31-corpus-edge-resolution.md): Spec: edge resolution analysis with per-type rates, pending edge ranking, and resolution velocity *(status: done)*
- [specs/2026-08-31-corpus-source-chain.md](specs/2026-08-31-corpus-source-chain.md): Spec: source provenance chain tracing supersession relationships with broken chain detection *(status: done)*
- [specs/2026-08-31-corpus-citation-analysis.md](specs/2026-08-31-corpus-citation-analysis.md): Spec: citation analysis with top targets, per-source coverage, verification rates, and uncited claim detection *(status: done)*
- [specs/2026-08-31-corpus-chunk-evolution.md](specs/2026-08-31-corpus-chunk-evolution.md): Spec: chunk evolution tracking most-revised chunks, content drift statistics, and per-chunk version history *(status: done)*
- [specs/2026-08-31-corpus-artifact-adoption.md](specs/2026-08-31-corpus-artifact-adoption.md): Spec: artifact adoption analysis with implementation rates, per-source density, and orphan detection *(status: done)*
- [specs/2026-08-31-corpus-domain-analysis.md](specs/2026-08-31-corpus-domain-analysis.md): Spec: domain analysis with distribution, per-source breakdown, multi-domain detection, and inter-domain edge flow *(status: done)*
- [specs/2026-08-31-corpus-tag-landscape.md](specs/2026-08-31-corpus-tag-landscape.md): Spec: tag landscape with frequency distribution, per-source profiles, edge-tag correlation, and score bands *(status: done)*
- [specs/2026-08-31-corpus-similarity-analysis.md](specs/2026-08-31-corpus-similarity-analysis.md): Spec: similarity analysis with score distribution, closest pairs, outlier review, and cluster cohesion *(status: done)*
- [specs/2026-08-31-corpus-health-scorecard.md](specs/2026-08-31-corpus-health-scorecard.md): Spec: unified health scorecard aggregating all signal tables into per-dimension quality scores *(status: done)*
- [specs/2026-08-31-corpus-freshness-scorer.md](specs/2026-08-31-corpus-freshness-scorer.md): Spec: per-chunk freshness scoring from temporal signals with exponential decay and multi-table correlation *(status: done)*
- [specs/2026-08-31-corpus-claim-consensus.md](specs/2026-08-31-corpus-claim-consensus.md): Spec: cross-source claim consensus analyzer measuring agreement and contradiction across independent sources *(status: done)*
- [specs/2026-08-31-corpus-ingestion-regression.md](specs/2026-08-31-corpus-ingestion-regression.md): Spec: ingestion regression detector comparing chunk versions for quality drops *(status: done)*
- [specs/2026-08-31-corpus-artifact-graph.md](specs/2026-08-31-corpus-artifact-graph.md): Spec: artifact dependency graph mapping co-mention, co-source, and claim-linked relationships between artifacts *(status: done)*
- [specs/2026-08-31-corpus-query-coverage.md](specs/2026-08-31-corpus-query-coverage.md): Spec: query coverage analyzer finding chunks unreachable by FTS5 probe queries *(status: done)*
- [specs/2026-08-31-corpus-source-provenance.md](specs/2026-08-31-corpus-source-provenance.md): Spec: source provenance scorer combining license, liveness, acceptance, citation, and freshness signals *(status: done)*
- [specs/2026-08-31-corpus-domain-tag-affinity.md](specs/2026-08-31-corpus-domain-tag-affinity.md): Spec: domain-tag affinity analysis using pointwise mutual information across chunk_domains and chunk_tags *(status: done)*
- [specs/2026-08-31-corpus-readability.md](specs/2026-08-31-corpus-readability.md): Spec: chunk readability scorer measuring text complexity from word length, type-token ratio, and long word density *(status: done)*
- [specs/2026-08-31-corpus-edge-density.md](specs/2026-08-31-corpus-edge-density.md): Spec: claim edge density measuring network interconnectedness per source with island detection *(status: done)*
- [specs/2026-08-31-corpus-citation-age.md](specs/2026-08-31-corpus-citation-age.md): Spec: citation verification age measuring staleness of citation checks and overdue re-verification *(status: done)*
- [specs/2026-08-31-corpus-domain-balance.md](specs/2026-08-31-corpus-domain-balance.md): Spec: domain coverage balance measuring distribution evenness with Shannon entropy and Gini coefficient *(status: done)*
- [specs/2026-08-31-corpus-source-citation-net.md](specs/2026-08-31-corpus-source-citation-net.md): Spec: source-to-source citation network aggregating chunk citations to source-level dependency topology *(status: done)*
- [specs/2026-08-31-corpus-version-churn.md](specs/2026-08-31-corpus-version-churn.md): Spec: version churn rate measuring temporal revision velocity and hotspot detection *(status: done)*
- [specs/2026-08-31-corpus-tag-entropy.md](specs/2026-08-31-corpus-tag-entropy.md): Spec: tag entropy measuring information content and surprise of per-chunk tag assignments *(status: done)*
- [specs/2026-08-31-corpus-cross-ref-density.md](specs/2026-08-31-corpus-cross-ref-density.md): Spec: cross-reference density measuring internal vs external citation patterns and source insularity *(status: done)*
- [specs/2026-08-31-corpus-edge-confidence.md](specs/2026-08-31-corpus-edge-confidence.md): Spec: edge confidence calibration measuring claim edge confidence distribution and extremes per edge type *(status: done)*
- [specs/2026-08-31-corpus-source-lifecycle.md](specs/2026-08-31-corpus-source-lifecycle.md): Spec: source lifecycle measuring ingestion lag, liveness distribution, and kind profiles *(status: done)*
- [specs/2026-08-31-corpus-chunk-kind-profile.md](specs/2026-08-31-corpus-chunk-kind-profile.md): Spec: chunk kind profile measuring kind distribution across sources and domains *(status: done)*
- [specs/2026-08-31-corpus-citation-verification.md](specs/2026-08-31-corpus-citation-verification.md): Spec: citation verification rate measuring verified vs unverified citation patterns per source and tag *(status: done)*
- [specs/2026-08-31-corpus-word-count-distribution.md](specs/2026-08-31-corpus-word-count-distribution.md): Spec: word count distribution measuring chunk length patterns, per-kind statistics, and outlier detection *(status: done)*
- [specs/2026-08-31-corpus-simhash-distribution.md](specs/2026-08-31-corpus-simhash-distribution.md): Spec: simhash distribution measuring hash-space density, bit entropy, collision patterns, and popcount balance *(status: done)*
- [specs/2026-08-31-corpus-domain-score-distribution.md](specs/2026-08-31-corpus-domain-score-distribution.md): Spec: domain score distribution measuring classification confidence patterns and low-confidence assignments *(status: done)*
- [specs/2026-08-31-corpus-status-reason-trends.md](specs/2026-08-31-corpus-status-reason-trends.md): Spec: status reason trends tracking quarantine and rejection patterns over time, by source, and by kind *(status: done)*
- [specs/2026-08-31-corpus-tag-score-trends.md](specs/2026-08-31-corpus-tag-score-trends.md): Spec: tag score trends measuring tagging confidence evolution, per-tag drift detection, and classifier health *(status: done)*
- [specs/2026-08-31-corpus-source-size-distribution.md](specs/2026-08-31-corpus-source-size-distribution.md): Spec: source size distribution, byte-count patterns and outlier detection across sources *(status: done)*
- [specs/2026-08-31-corpus-edge-basis-analysis.md](specs/2026-08-31-corpus-edge-basis-analysis.md): Spec: edge basis analysis, claim justification text coverage and quality patterns *(status: done)*
- [specs/2026-08-31-corpus-citation-locator-analysis.md](specs/2026-08-31-corpus-citation-locator-analysis.md): Spec: citation locator analysis, locator completeness and format patterns *(status: done)*
- [specs/2026-08-31-corpus-publisher-license-distribution.md](specs/2026-08-31-corpus-publisher-license-distribution.md): Spec: publisher and license distribution, concentration metrics and cross-tabulation *(status: done)*
- [specs/2026-08-31-corpus-citation-tag-profile.md](specs/2026-08-31-corpus-citation-tag-profile.md): Spec: citation tag profile, cross-dimensional tag analysis against source kinds and domains *(status: done)*
- [specs/2026-08-31-corpus-heading-depth-analysis.md](specs/2026-08-31-corpus-heading-depth-analysis.md): Spec: heading depth analysis, document structure patterns from heading paths *(status: done)*
- [specs/2026-08-31-corpus-language-distribution.md](specs/2026-08-31-corpus-language-distribution.md): Spec: language distribution, per-source diversity and kind correlation from chunk lang tags *(status: done)*
- [specs/2026-08-31-corpus-upstream-provenance.md](specs/2026-08-31-corpus-upstream-provenance.md): Spec: upstream provenance analysis, revision and modification time completeness and age distribution *(status: done)*
- [specs/2026-08-31-corpus-artifact-version-analysis.md](specs/2026-08-31-corpus-artifact-version-analysis.md): Spec: artifact version and snippet analysis, version format classification and snippet coverage *(status: done)*
- [specs/2026-08-31-corpus-version-domain-stability.md](specs/2026-08-31-corpus-version-domain-stability.md): Spec: version-domain stability, chunk_versions crossed with chunk_domains to measure churn by domain and identify volatile chunks *(status: done)*
- [specs/2026-08-31-corpus-artifact-edge-profile.md](specs/2026-08-31-corpus-artifact-edge-profile.md): Spec: artifact-edge profile, artifact_type and implementation status cross-tabulated against edge_type and confidence *(status: done)*
- [specs/2026-08-31-corpus-source-composite-profile.md](specs/2026-08-31-corpus-source-composite-profile.md): Spec: source composite profile, per-source richness vector across all six metadata tables *(status: done)*
- [specs/2026-08-31-corpus-tag-verification-breakdown.md](specs/2026-08-31-corpus-tag-verification-breakdown.md): Spec: tag-verification breakdown, chunk_tags joined with individual citation rows for per-tag verification rates *(status: done)*
- [specs/2026-08-31-corpus-edge-citation-quality.md](specs/2026-08-31-corpus-edge-citation-quality.md): Spec: edge citation quality, three-way join of claim_edges with citations at both endpoints for per-edge citation backing analysis *(status: done)*
- [specs/2026-08-31-corpus-artifact-citation-provenance.md](specs/2026-08-31-corpus-artifact-citation-provenance.md): Spec: artifact citation provenance, three-way join of artifacts with citations via chunk_id for per-artifact evidentiary backing *(status: done)*
- [specs/2026-08-31-corpus-supersession-edge-orphans.md](specs/2026-08-31-corpus-supersession-edge-orphans.md): Spec: supersession edge orphans, three-way consistency check finding claim_edges stranded by source supersession *(status: done)*
- [specs/2026-08-31-corpus-license-edge-analysis.md](specs/2026-08-31-corpus-license-edge-analysis.md): Spec: license edge analysis, claim edges stratified by source license verdict with cross-boundary and blocked source detection *(status: done)*
- [specs/2026-08-31-corpus-artifact-version-conflicts.md](specs/2026-08-31-corpus-artifact-version-conflicts.md): Spec: artifact version conflicts, four-way join detecting same-name different-version artifacts across claim_edge endpoints *(status: done)*
- [specs/2026-08-31-corpus-edge-reachability.md](specs/2026-08-31-corpus-edge-reachability.md): Spec: edge reachability, multi-hop BFS path analysis of the claim_edges graph with diameter, shortest path, and hop distribution *(status: done)*
- [specs/2026-08-31-corpus-evidence-chain-audit.md](specs/2026-08-31-corpus-evidence-chain-audit.md): Spec: evidence chain audit, four-way join auditing full provenance from sources through chunks to citations and artifacts *(status: done)*
- [specs/2026-08-31-corpus-version-edge-impact.md](specs/2026-08-31-corpus-version-edge-impact.md): Spec: version edge impact, temporal join of chunk_versions with claim_edges to detect stale edges after content revisions *(status: done)*
- [specs/2026-08-31-corpus-version-citation-drift.md](specs/2026-08-31-corpus-version-citation-drift.md): Spec: version citation drift, temporal join of chunk_versions with citations to detect stale verification after content revisions *(status: done)*
- [specs/2026-08-31-corpus-version-tag-stability.md](specs/2026-08-31-corpus-version-tag-stability.md): Spec: version tag stability, temporal join of chunk_versions with chunk_tags to detect stale tags after content revisions *(status: done)*
- [specs/2026-08-31-corpus-artifact-domain-distribution.md](specs/2026-08-31-corpus-artifact-domain-distribution.md): Spec: artifact domain distribution, join of artifacts with chunk_domains showing which domains contain which artifact types *(status: done)*
- [specs/2026-08-31-corpus-tag-citation-correlation.md](specs/2026-08-31-corpus-tag-citation-correlation.md): Spec: tag citation correlation, join of chunk_tags with citations measuring citation density and verification rate per tag *(status: done)*
- [specs/2026-08-31-corpus-domain-citation-profile.md](specs/2026-08-31-corpus-domain-citation-profile.md): Spec: domain citation profile, join of chunk_domains with citations measuring citation density and verification rate per domain *(status: done)*
- [specs/2026-08-31-corpus-tag-edge-correlation.md](specs/2026-08-31-corpus-tag-edge-correlation.md): Spec: tag edge correlation, join of chunk_tags with claim_edges measuring edge density and type distribution per tag *(status: done)*
- [specs/2026-08-31-corpus-domain-edge-depth.md](specs/2026-08-31-corpus-domain-edge-depth.md): Spec: domain edge depth, join of chunk_domains with claim_edges measuring edge density and type distribution per domain *(status: done)*
- [specs/2026-08-31-corpus-artifact-tag-profile.md](specs/2026-08-31-corpus-artifact-tag-profile.md): Spec: artifact tag profile, join of artifacts with chunk_tags showing tag co-occurrence with artifact types *(status: done)*
- [specs/2026-08-31-corpus-version-source-profile.md](specs/2026-08-31-corpus-version-source-profile.md): Spec: version source profile, join of chunk_versions with sources measuring revision activity per source and source kind *(status: done)*
- [specs/2026-08-31-corpus-source-enrichment-completeness.md](specs/2026-08-31-corpus-source-enrichment-completeness.md): Spec: source enrichment completeness, six-dimension enrichment coverage per source with gap detection *(status: done)*
- [specs/2026-08-31-corpus-enrichment-lag-profile.md](specs/2026-08-31-corpus-enrichment-lag-profile.md): Spec: enrichment lag profile, temporal lag between chunk ingestion and enrichment events *(status: done)*
- [specs/2026-08-31-corpus-fts-citation-reachability.md](specs/2026-08-31-corpus-fts-citation-reachability.md): Spec: FTS citation reachability, citation density relative to FTS word count with searchability flags *(status: done)*
- [specs/2026-08-31-corpus-fts-edge-reachability.md](specs/2026-08-31-corpus-fts-edge-reachability.md): Spec: FTS edge reachability, edge density relative to FTS word count with searchability flags *(status: done)*
- [specs/2026-08-31-corpus-version-fts-coverage.md](specs/2026-08-31-corpus-version-fts-coverage.md): Spec: version FTS coverage, word count evolution across chunk revisions with churn measurement *(status: done)*
- [specs/2026-08-31-corpus-cross-table-outlier-detector.md](specs/2026-08-31-corpus-cross-table-outlier-detector.md): Spec: cross-table outlier detector, z-score anomalies across chunks, edges, and citations *(status: done)*
- [specs/2026-08-31-corpus-version-claim-edge-cascade.md](specs/2026-08-31-corpus-version-claim-edge-cascade.md): Spec: version claim edge cascade, edge distribution across chunk version depths *(status: done)*
- [specs/2026-08-31-corpus-status-enrichment-profile.md](specs/2026-08-31-corpus-status-enrichment-profile.md): Spec: status enrichment profile, enrichment depth per chunk status with gap detection *(status: done)*
- [specs/2026-08-31-corpus-heading-tag-correlation.md](specs/2026-08-31-corpus-heading-tag-correlation.md): Spec: heading tag correlation, tag distribution and diversity across heading paths and depths *(status: done)*
- [specs/2026-08-31-corpus-publisher-tag-profile.md](specs/2026-08-31-corpus-publisher-tag-profile.md): Spec: publisher tag profile, tag vocabulary distribution across publishers with concentration analysis *(status: done)*
- [specs/2026-08-31-corpus-simhash-edge-profile.md](specs/2026-08-31-corpus-simhash-edge-profile.md): Spec: simhash edge profile, claim edge patterns across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-status-profile.md](specs/2026-08-31-corpus-simhash-status-profile.md): Spec: simhash status profile, chunk status distribution and quality consistency across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-kind-profile.md](specs/2026-08-31-corpus-simhash-kind-profile.md): Spec: simhash kind profile, source kind distribution and cross-format duplication across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-liveness-profile.md](specs/2026-08-31-corpus-simhash-liveness-profile.md): Spec: simhash liveness profile, source liveness distribution and maintenance duplication across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-publisher-profile.md](specs/2026-08-31-corpus-simhash-publisher-profile.md): Spec: simhash publisher profile, publisher distribution across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-license-profile.md](specs/2026-08-31-corpus-simhash-license-profile.md): Spec: simhash license profile, license distribution across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-tag-profile.md](specs/2026-08-31-corpus-simhash-tag-profile.md): Spec: simhash tag profile, tag vocabulary distribution across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-domain-profile.md](specs/2026-08-31-corpus-simhash-domain-profile.md): Spec: simhash domain profile, semantic domain distribution across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-simhash-citation-profile.md](specs/2026-08-31-corpus-simhash-citation-profile.md): Spec: simhash citation profile, citation count distribution across simhash collision groups *(status: done)*
- [specs/2026-08-31-corpus-heading-tag-profile.md](specs/2026-08-31-corpus-heading-tag-profile.md): Spec: heading tag profile, tag vocabulary distribution across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-domain-profile.md](specs/2026-08-31-corpus-heading-domain-profile.md): Spec: heading domain profile, semantic domain distribution across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-citation-profile.md](specs/2026-08-31-corpus-heading-citation-profile.md): Spec: heading citation profile, citation count distribution across heading paths *(status: done)*
- [specs/2026-08-31-corpus-kind-tag-profile.md](specs/2026-08-31-corpus-kind-tag-profile.md): Spec: kind tag profile, tag vocabulary distribution across chunk kinds *(status: done)*
- [specs/2026-08-31-corpus-license-tag-profile.md](specs/2026-08-31-corpus-license-tag-profile.md): Spec: license tag profile, tag vocabulary distribution across license types *(status: done)*
- [specs/2026-08-31-corpus-publisher-domain-profile.md](specs/2026-08-31-corpus-publisher-domain-profile.md): Spec: publisher domain profile, semantic domain distribution across publishers *(status: done)*
- [specs/2026-08-31-corpus-license-domain-profile.md](specs/2026-08-31-corpus-license-domain-profile.md): Spec: license domain profile, semantic domain distribution across license types *(status: done)*
- [specs/2026-08-31-corpus-kind-domain-profile.md](specs/2026-08-31-corpus-kind-domain-profile.md): Spec: kind domain profile, semantic domain distribution across chunk kinds *(status: done)*
- [specs/2026-08-31-corpus-heading-domain-correlation.md](specs/2026-08-31-corpus-heading-domain-correlation.md): Spec: heading domain correlation, semantic domain distribution across heading paths and depths *(status: done)*
- [specs/2026-08-31-corpus-heading-edge-correlation.md](specs/2026-08-31-corpus-heading-edge-correlation.md): Spec: heading edge correlation, claim edge distribution and type diversity across heading paths and depths *(status: done)*
- [specs/2026-08-31-corpus-publisher-citation-profile.md](specs/2026-08-31-corpus-publisher-citation-profile.md): Spec: publisher citation profile, citation distribution and verification rates across publishers *(status: done)*
- [specs/2026-08-31-corpus-publisher-edge-profile.md](specs/2026-08-31-corpus-publisher-edge-profile.md): Spec: publisher edge profile, claim edge distribution and cross-publisher edge patterns *(status: done)*
- [specs/2026-08-31-corpus-publisher-liveness-profile.md](specs/2026-08-31-corpus-publisher-liveness-profile.md): Spec: publisher liveness profile, source liveness distribution and maintenance patterns per publisher *(status: done)*
- [specs/2026-08-31-corpus-publisher-status-profile.md](specs/2026-08-31-corpus-publisher-status-profile.md): Spec: publisher status profile, chunk status distribution and acceptance rates across publishers *(status: done)*
- [specs/2026-08-31-corpus-license-liveness-profile.md](specs/2026-08-31-corpus-license-liveness-profile.md): Spec: license liveness profile, liveness distribution and maintenance patterns per license type *(status: done)*
- [specs/2026-08-31-corpus-license-status-profile.md](specs/2026-08-31-corpus-license-status-profile.md): Spec: license status profile, chunk status distribution and acceptance rates across license types *(status: done)*
- [specs/2026-08-31-corpus-kind-liveness-profile.md](specs/2026-08-31-corpus-kind-liveness-profile.md): Spec: kind liveness profile, liveness distribution and maintenance patterns per source kind *(status: done)*
- [specs/2026-08-31-corpus-kind-status-profile.md](specs/2026-08-31-corpus-kind-status-profile.md): Spec: kind status profile, chunk status distribution and acceptance rates across source kinds *(status: done)*
- [specs/2026-08-31-corpus-liveness-status-profile.md](specs/2026-08-31-corpus-liveness-status-profile.md): Spec: liveness status profile, chunk quality distribution across source liveness states *(status: done)*
- [specs/2026-08-31-corpus-publisher-kind-profile.md](specs/2026-08-31-corpus-publisher-kind-profile.md): Spec: publisher kind profile, source kind distribution and format diversity per publisher *(status: done)*
- [specs/2026-08-31-corpus-license-kind-profile.md](specs/2026-08-31-corpus-license-kind-profile.md): Spec: license kind profile, source kind distribution and format coverage per license type *(status: done)*
- [specs/2026-08-31-corpus-heading-status-profile.md](specs/2026-08-31-corpus-heading-status-profile.md): Spec: heading status profile, chunk status distribution and section quality across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-liveness-profile.md](specs/2026-08-31-corpus-heading-liveness-profile.md): Spec: heading liveness profile, source liveness distribution and maintenance patterns across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-kind-profile.md](specs/2026-08-31-corpus-heading-kind-profile.md): Spec: heading kind profile, source kind distribution and format coverage across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-publisher-profile.md](specs/2026-08-31-corpus-heading-publisher-profile.md): Spec: heading publisher profile, publisher distribution and sourcing diversity across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-license-profile.md](specs/2026-08-31-corpus-heading-license-profile.md): Spec: heading license profile, license distribution and licensing diversity across heading paths *(status: done)*
- [specs/2026-08-31-corpus-heading-citation-correlation.md](specs/2026-08-31-corpus-heading-citation-correlation.md): Spec: heading citation correlation, citation distribution and verification rates across heading paths and depths *(status: done)*
- [specs/2026-08-31-corpus-kind-citation-profile.md](specs/2026-08-31-corpus-kind-citation-profile.md): Spec: kind citation profile, citation distribution and verification rates across chunk kinds *(status: done)*
- [specs/2026-08-31-corpus-kind-edge-profile.md](specs/2026-08-31-corpus-kind-edge-profile.md): Spec: kind edge profile, claim edge distribution and cross-kind edge patterns across chunk kinds *(status: done)*
- [specs/2026-08-31-corpus-license-citation-profile.md](specs/2026-08-31-corpus-license-citation-profile.md): Spec: license citation profile, citation distribution and verification rates across license types *(status: done)*
- [specs/2026-08-31-corpus-liveness-citation-profile.md](specs/2026-08-31-corpus-liveness-citation-profile.md): Spec: liveness citation profile, citation distribution and verification rates across source liveness states *(status: done)*
- [specs/2026-08-31-corpus-liveness-domain-profile.md](specs/2026-08-31-corpus-liveness-domain-profile.md): Spec: liveness domain profile, chunk domain distribution and knowledge breadth across source liveness states *(status: done)*
- [specs/2026-08-31-corpus-liveness-edge-profile.md](specs/2026-08-31-corpus-liveness-edge-profile.md): Spec: liveness edge profile, claim edge distribution and cross-liveness edge patterns across source liveness states *(status: done)*
- [specs/2026-08-31-corpus-liveness-tag-profile.md](specs/2026-08-31-corpus-liveness-tag-profile.md): Spec: liveness tag profile, chunk tag distribution and vocabulary diversity across source liveness states *(status: done)*
- [specs/2026-08-31-corpus-status-citation-profile.md](specs/2026-08-31-corpus-status-citation-profile.md): Spec: status citation profile, citation distribution and verification rates across chunk statuses *(status: done)*
- [specs/2026-08-31-corpus-status-domain-profile.md](specs/2026-08-31-corpus-status-domain-profile.md): Spec: status domain profile, chunk domain distribution and knowledge breadth across chunk statuses *(status: done)*
- [specs/2026-08-31-corpus-status-edge-profile.md](specs/2026-08-31-corpus-status-edge-profile.md): Spec: status edge profile, claim edge distribution and cross-status edge patterns across chunk statuses *(status: done)*
- [specs/2026-08-31-corpus-status-tag-profile.md](specs/2026-08-31-corpus-status-tag-profile.md): Spec: status tag profile, chunk tag distribution and vocabulary diversity across chunk statuses *(status: done)*
- [specs/2026-08-31-corpus-tag-domain-correlation.md](specs/2026-08-31-corpus-tag-domain-correlation.md): Spec: tag domain correlation, chunk tag and domain co-occurrence patterns and pair density *(status: done)*
- [specs/2026-08-31-corpus-tag-citation-yield.md](specs/2026-08-31-corpus-tag-citation-yield.md): Spec: tag-citation yield, chunk_tags.tag correlated with citation count to identify highest-yield topical tags *(status: done)*
- [specs/2026-08-31-corpus-version-timeline.md](specs/2026-08-31-corpus-version-timeline.md): Spec: version timeline, chunk_versions.snapshot_utc temporal distribution with depth bucketing and churn measurement *(status: done)*
- [specs/2026-08-31-corpus-classification-timeline.md](specs/2026-08-31-corpus-classification-timeline.md): Spec: classification timeline, chunk_domains.classified_utc temporal distribution with per-domain activity and score trends *(status: done)*
- [specs/2026-08-31-corpus-verification-timeline.md](specs/2026-08-31-corpus-verification-timeline.md): Spec: verification timeline, citations.verified_utc temporal distribution with tag stratification and ingestion-to-verification lag *(status: done)*
- [specs/2026-08-31-corpus-supersession-analysis.md](specs/2026-08-31-corpus-supersession-analysis.md): Spec: supersession analysis, sources.supersedes population rates, chain depth distribution, and per-kind supersession patterns *(status: done)*
- [specs/2026-08-31-corpus-cross-kind-analysis.md](specs/2026-08-31-corpus-cross-kind-analysis.md): Spec: cross-kind analysis, chunk kind, artifact type, and citation density cross-tabulated against source kind *(status: done)*
- [specs/2026-08-31-corpus-edge-detection-timeline.md](specs/2026-08-31-corpus-edge-detection-timeline.md): Spec: edge detection timeline, claim_edges.detected_utc temporal analysis with resolution lag *(status: done)*
- [specs/2026-08-31-corpus-evidence-coverage.md](specs/2026-08-31-corpus-evidence-coverage.md): Spec: evidence coverage analysis, evidence_path population rates and path pattern classification *(status: done)*
- [specs/2026-08-31-corpus-artifact-name-analysis.md](specs/2026-08-31-corpus-artifact-name-analysis.md): Spec: artifact name analysis, name frequency, multi-source overlap, and implementation rate per artifact name *(status: done)*
- [specs/2026-08-31-corpus-chunk-position-analysis.md](specs/2026-08-31-corpus-chunk-position-analysis.md): Spec: chunk position analysis, ordinal distribution and positional patterns for kind and citation density *(status: done)*
- [specs/2026-08-31-corpus-temporal-distribution.md](specs/2026-08-31-corpus-temporal-distribution.md): Spec: temporal distribution analysis, ingestion and publication timelines with fetch lag bucketing *(status: done)*
- [specs/2026-08-31-corpus-liveness-cross-analysis.md](specs/2026-08-31-corpus-liveness-cross-analysis.md): Spec: liveness cross-analysis, liveness patterns across kind, publisher, and license dimensions *(status: done)*
- [specs/2026-08-30-corpus-enrich.md](specs/2026-08-30-corpus-enrich.md): Spec: corpus entity enrichment, named entity extraction and artifact table linking with implementation evidence *(status: done)*
- [specs/2026-08-30-corpus-cite-gate.md](specs/2026-08-30-corpus-cite-gate.md): Spec: corpus citation gate, stage 4 enforcement quarantining uncited claim chunks *(status: done)*
- [specs/2026-08-30-corpus-normalise.md](specs/2026-08-30-corpus-normalise.md): Spec: corpus text normaliser, stage 0 NFC unicode, mojibake repair, dash mapping, and whitespace stripping *(status: done)*
- [specs/2026-08-30-corpus-chunker.md](specs/2026-08-30-corpus-chunker.md): Spec: corpus document chunker, stage 2 heading-based splitting with paragraph subdivision and kind classification *(status: done)*
- [specs/2026-08-30-corpus-paper-rule.md](specs/2026-08-30-corpus-paper-rule.md): Spec: corpus paper rule, stage 7 enforcement of 2026-only paper admission with publisher verification *(status: done)*
- [specs/2026-08-30-corpus-tag-store.md](specs/2026-08-30-corpus-tag-store.md): Spec: corpus tag store, persists auto-tagger results into chunk_tags table for faceted queries *(status: done)*
- [specs/2026-08-30-corpus-batch-export.md](specs/2026-08-30-corpus-batch-export.md): Spec: corpus batch export, adds tag/source-kind/date-range filters and tags field to export records *(status: done)*
- [specs/2026-08-30-corpus-chunk-versions.md](specs/2026-08-30-corpus-chunk-versions.md): Spec: corpus chunk versioning, tracks content changes across re-ingestions with hash-based snapshots *(status: done)*
- [specs/2026-08-30-corpus-domain-store.md](specs/2026-08-30-corpus-domain-store.md): Spec: corpus domain store, persists ML-based semantic domain classifications into chunk_domains table *(status: done)*
- [specs/2026-08-30-corpus-semantic-dedup.md](specs/2026-08-30-corpus-semantic-dedup.md): Spec: corpus semantic deduplication, embedding-based paraphrase detection using PCA-reduced TF-IDF vectors *(status: done)*
- [specs/2026-08-30-corpus-cluster-store.md](specs/2026-08-30-corpus-cluster-store.md): Spec: corpus cluster store, persists ML-based KMeans cluster assignments into chunk_clusters table *(status: done)*
- [specs/2026-08-30-corpus-similarity-store.md](specs/2026-08-30-corpus-similarity-store.md): Spec: corpus similarity store, precomputed nearest-neighbor pairs from embedding vectors *(status: done)*
- [specs/2026-08-30-corpus-outlier-store.md](specs/2026-08-30-corpus-outlier-store.md): Spec: corpus outlier store, persists ML-based topical isolation detection into chunk_outliers table *(status: done)*
- [HANDOFF-2026-08-05-session-close.md](HANDOFF-2026-08-05-session-close.md): Handoff: the atlas session, what landed and what is left *(status: historical-record)*
- [prd/2026-08-03-unified-architecture.md](prd/2026-08-03-unified-architecture.md): PRD: Unified architecture, the whole Claude OS in one flow *(status: proposed)*
- [prd/2026-08-03-boundary-termination-instrument.md](prd/2026-08-03-boundary-termination-instrument.md): PRD: BOUNDARY, the termination instrument *(status: proposed)*
- [prd/2026-07-30-consolidation-and-migration.md](prd/2026-07-30-consolidation-and-migration.md): PRD: Consolidation, document mapping, and the Linux migration *(status: APPROVED for autonomous execution )*
- [prd/autonomy-ecosystem.md](prd/autonomy-ecosystem.md): PRD: Autonomy Ecosystem (Claude OS v2) *(status: living)*
- [prd/claude-os.md](prd/claude-os.md): PRD: Claude OS (personal Claude control plane) *(status: active)*

## Standards

- [standards/agentic-repo-standard.md](standards/agentic-repo-standard.md): Root agentic repository standard *(status: active)*

## ADRs

- [0001](adr/0001-claude-setup-as-canonical-os-repo.md): claude-setup is the canonical OS repo
- [0002](adr/0002-subscription-oauth-over-metered-api.md): Subscription OAuth token, not metered API key, for all fleet auth
- [0003](adr/0003-native-push-over-onesignal.md): Native Claude push for the personal approvals rail, not OneSignal
- [0004](adr/0004-two-model-agreement-gate.md): PR review uses a two-model agreement gate
- [0005](adr/0005-enforcement-over-prose.md): Enforcement over prose (hooks/gates bind, CLAUDE.md requests)
- [0006](adr/0006-one-scheduler-topology.md): One scheduler topology: native cron local + cloud routines
- [0007](adr/0007-codex-reviewer-only.md): Second reviewer = free different-family models (Codex removed)
- [0008](adr/0008-reputation-from-external-truth-only.md): Persona reputation is computed from external ground truth ONLY
- [0009](adr/0009-slm-swarm-asymmetric-leaf-executors.md): SLM swarm = asymmetric leaf executors + trace flywheel (not a debate swarm)
- [0010](adr/0010-sessions-are-ephemeral-disk-is-memory.md): Sessions are ephemeral; disk is the only memory
- [0011](adr/0011-one-operational-state-db.md): One operational state DB (ecosystem.db), seeded from intent-control-plane
- [0012](adr/0012-autonomy-ships-only-via-pr-gate.md): Autonomous work ships ONLY through PR + review gate
- [0013](adr/0013-session-topology-concierge-plus-lanes.md): Session topology: one concierge + three chartered lanes
- [0014](adr/0014-social-publish-draft-first-hard-gate.md): Social publishing is draft-first behind a hard phone-approval gate
- [0015](adr/0015-opus5-default-fable-exceptional.md): Opus 5 is the lead default; Fable is exceptional-only
- [0016](adr/0016-lane-letters-renumbered-a-through-d.md): Lane letters renumbered B/C/D/E to A/B/C/D
- [0017](adr/0017-intent-control-plane-lives-in-claude-setup.md): intent-control-plane is authoritative in claude-setup; the new-recruit copy is redundant
- [0018](adr/0018-two-tier-inter-agent-channel.md): inter-agent messages get two channels, and the dense one carries an oracle
- [0019](adr/0019-supply-chain-verification.md): third-party tools are adopted on recorded evidence, not refused on principle
- [0020](adr/0020-agentic-repo-standard.md): one repository standard for the estate, enforced by adopted alint
- [0021](adr/0021-rust-for-hot-paths-python-for-oracles.md): Rust for hot paths and boundaries, Python for oracles; first named rewrite is bus.py

## Specs

- [specs/2026-07-23-persona-review-economy.md](specs/2026-07-23-persona-review-economy.md): Spec: Persona Review Economy (a dynamic labor market of reviewers) *(status: active)*
- [specs/2026-07-23-slm-swarm.md](specs/2026-07-23-slm-swarm.md): Spec: SLM Swarm (how we actually use small models) *(status: active)*
- [specs/2026-07-24-autonomy-implementation.md](specs/2026-07-24-autonomy-implementation.md): Implementation spec: Autonomy Ecosystem *(status: active)*
- [specs/2026-07-24-command-center-superior.md](specs/2026-07-24-command-center-superior.md): Spec: FleetView: a superior command center over the Claude OS *(status: active)*
- [specs/2026-07-29-architecture-build-plan-v2.md](specs/2026-07-29-architecture-build-plan-v2.md): Architecture build plan v2, 2026-07-29 (supersedes v1 the same day) *(status not declared)*
- [specs/2026-07-29-architecture-build-plan.md](specs/2026-07-29-architecture-build-plan.md): Architecture build plan, merged 2026-07-29 (plan of record) *(status not declared)*
- [specs/2026-07-29-decision-rules.md](specs/2026-07-29-decision-rules.md): Decision rules: when to use what *(status: proposed)*
- [specs/2026-07-29-deterministic-preflight.md](specs/2026-07-29-deterministic-preflight.md): Deterministic preflight: proposal (not built) *(status: PROPOSAL, operator-originated 2026)*
- [specs/2026-07-29-intent-traceability.md](specs/2026-07-29-intent-traceability.md): Intent traceability: wiring, not building *(status not declared)*
- [specs/2026-07-29-prompt-to-ticket-lifecycle.md](specs/2026-07-29-prompt-to-ticket-lifecycle.md): Implementation spec: prompt-to-ticket lifecycle *(status: active)*
- [specs/2026-07-29-trace-model-sacred-timeline.md](specs/2026-07-29-trace-model-sacred-timeline.md): Trace model: worldlines, cones, and one canonical branch *(status not declared)*
- [specs/2026-07-30-data-architecture-and-orchestration.md](specs/2026-07-30-data-architecture-and-orchestration.md): Data architecture and orchestration: what SQLite is for, what git is for, and what shape the DAG actually is *(status: PROPOSAL, pending operator approva)*
- [specs/2026-07-31-agentic-directory-standard-sota.md](specs/2026-07-31-agentic-directory-standard-sota.md): SOTA Agentic Repository Directory Standard & Estate Enhancement Plan *(status: SPECIFICATION & ARCHITECTURAL COMP)*
- [specs/2026-07-31-github-native-project-surface.md](specs/2026-07-31-github-native-project-surface.md): GitHub-native project surface for ShovalBenjer/claude-setup and Zion (project 3) *(status: DESIGN)*
- [specs/2026-07-31-kanban-four-layer-model.md](specs/2026-07-31-kanban-four-layer-model.md): The four-layer board, fitted to claude-setup *(status: DESIGN)*
- [specs/2026-07-31-project-federation.md](specs/2026-07-31-project-federation.md): Per-repo project federation for the ShovalBenjer estate, and why it is not built *(status not declared)*
- [specs/2026-07-31-research-corpus-and-cache.md](specs/2026-07-31-research-corpus-and-cache.md): Research corpus and cache (row-reuse, cache2action) *(status not declared)*
- [specs/2026-07-31-zion-board-as-product-instrument.md](specs/2026-07-31-zion-board-as-product-instrument.md): Zion as a product instrument, not a task list *(status: active)*
- [specs/2026-10-09-review-cache-tiers.md](specs/2026-10-09-review-cache-tiers.md): Spec: tiered memoized review decisions + trigger-conditioned persona execution, exact/normalized/semantic tiers with full conditioning, anti-loop guard, Table 11-3 cost accounting (#372) *(status: active)*

## Analysis (point-in-time, inputs to TODO, never a decision)

- [analysis/2026-07-23-local-model-stress-test.md](analysis/2026-07-23-local-model-stress-test.md): Local model stress test: 2026-07-23 *(status not declared)*
- [analysis/2026-07-24-creativity-wow-gap.md](analysis/2026-07-24-creativity-wow-gap.md): Creativity / wow / deliberation-texture gap analysis *(status not declared)*
- [analysis/2026-07-24-deployment-gap-audit.md](analysis/2026-07-24-deployment-gap-audit.md): Deployment gap audit: claimed setup vs live harness, 2026-07-24 *(status not declared)*
- [analysis/2026-07-24-fleet-verification-gap.md](analysis/2026-07-24-fleet-verification-gap.md): Why the reference Opus 5 run shipped a game and this setup ships documents *(status not declared)*
- [analysis/2026-07-24-reference-repos-excavation.md](analysis/2026-07-24-reference-repos-excavation.md): Excavation: two WhatsApp-saved repos (amirfish1/claude-command-center, Master0fFate/just-my-skills) *(status: point-in-time scan, per docs-contr)*
- [analysis/2026-07-24-research-wiring-audit.md](analysis/2026-07-24-research-wiring-audit.md): Research-wiring audit + AUTO-17 pipeline design: 2026-07-24 *(status not declared)*
- [analysis/2026-07-24-setup-holding-us-back.md](analysis/2026-07-24-setup-holding-us-back.md): Is the setup holding us back? Synthesis of 5 audit lanes, 2026-07-24 *(status not declared)*
- [analysis/2026-07-24-skills-wiring-audit.md](analysis/2026-07-24-skills-wiring-audit.md): Skills-estate wiring audit: 2026-07-24 *(status not declared)*
- [analysis/2026-07-24-work-archive-import.md](analysis/2026-07-24-work-archive-import.md): Work-archive import: full sync of the work Claude setup (2026-07-24) *(status not declared)*
- [analysis/2026-07-25-claude-mastery-audit.md](analysis/2026-07-25-claude-mastery-audit.md): Claude Code Mastery, Evidence, and Learning-Corpus Audit *(status not declared)*
- [analysis/2026-07-25-claude-mastery-research-prompt.md](analysis/2026-07-25-claude-mastery-research-prompt.md): Claude Code mastery research prompt *(status not declared)*
- [analysis/2026-07-25-cloudflare-fit.md](analysis/2026-07-25-cloudflare-fit.md): Cloudflare fit audit: 2026-07-25 *(status not declared)*
- [analysis/2026-07-25-dynamic-setup-decisions.md](analysis/2026-07-25-dynamic-setup-decisions.md): Dynamic setup decisions: workflows, effort, thinking, cross-model, resources *(status: decision document, not a spec)*
- [analysis/2026-07-25-effort-and-thinking.md](analysis/2026-07-25-effort-and-thinking.md): Effort/thinking config audit: v2.1.219 binary evidence *(status: active)*
- [analysis/2026-07-25-free-tier-exploitables.md](analysis/2026-07-25-free-tier-exploitables.md): Free-tier exploitables: what closes the five open problems, 2026-07-25 *(status not declared)*
- [analysis/2026-07-25-other-resources.md](analysis/2026-07-25-other-resources.md): Other resources that can close the named weak points: 2026-07-25 *(status not declared)*
- [analysis/2026-07-25-our-own-dolt.md](analysis/2026-07-25-our-own-dolt.md): Can we build our own Dolt, and would it overcome theirs *(status not declared)*
- [analysis/2026-07-25-repo-benchmark-and-star-forensics.md](analysis/2026-07-25-repo-benchmark-and-star-forensics.md): Three-way repo benchmark and star forensics *(status not declared)*
- [analysis/2026-07-26-session-handoff.md](analysis/2026-07-26-session-handoff.md): Session handoff, 2026-07-26 *(status not declared)*
- [analysis/2026-07-27-research-transfer-uncertainty-and-oracles.md](analysis/2026-07-27-research-transfer-uncertainty-and-oracles.md): What the compile-once research says about THIS harness *(status not declared)*
- [analysis/2026-07-29-albert-prior-art-verdict.md](analysis/2026-07-29-albert-prior-art-verdict.md): Albert: prior art for the whole repository, and not adoptable *(status not declared)*
- [analysis/2026-07-29-local-dependency-audit.md](analysis/2026-07-29-local-dependency-audit.md): Local dependency audit, 2026-07-29 *(status not declared)*
- [analysis/2026-07-29-long-context-kernel-critique-response.md](analysis/2026-07-29-long-context-kernel-critique-response.md): The long-context kernel critique, tested against this repo's ledgers *(status not declared)*
- [analysis/2026-07-29-session-retro-modes-models-workflows-observability.md](analysis/2026-07-29-session-retro-modes-models-workflows-observability.md): Session retro, 2026-07-29 (lane B): modes, models, workflows, interruption, observability *(status not declared)*
- [analysis/2026-07-29-where-our-system-stands.md](analysis/2026-07-29-where-our-system-stands.md): Where our system stands against everything we researched *(status not declared)*
- [analysis/2026-07-30-context-engineering-and-the-absence-claim-class.md](analysis/2026-07-30-context-engineering-and-the-absence-claim-class.md): Context engineering, three absence claims in one session, and what /context showed *(status not declared)*
- [analysis/2026-07-30-github-repo-triage.md](analysis/2026-07-30-github-repo-triage.md): Saved GitHub repositories: first triage, and what it blocks *(status not declared)*
- [analysis/2026-07-30-native-surface-audit.md](analysis/2026-07-30-native-surface-audit.md): Claude Code native surface: what we wire, what we leave on the floor *(status not declared)*
- [analysis/2026-07-30-point-in-time-reconstruction.md](analysis/2026-07-30-point-in-time-reconstruction.md): Point-in-time reconstruction: what git already answers, and the narrow strip it does not *(status not declared)*
- [analysis/2026-07-30-self-chat-absorption-batch.md](analysis/2026-07-30-self-chat-absorption-batch.md): Self-chat absorption batch, 2026-07-30 *(status not declared)*
- [analysis/2026-07-31-density-gate-measurement.md](analysis/2026-07-31-density-gate-measurement.md): Density and variance: the measurement, and why no threshold was set *(status not declared)*
- [analysis/2026-07-31-the-green-test-gradient.md](analysis/2026-07-31-the-green-test-gradient.md): The green-test gradient, and two measurements of the bail-out path *(status not declared)*
- [analysis/reference/coherence-governor-AGENTS.md](analysis/reference/coherence-governor-AGENTS.md): Coherence Governor Agent *(status not declared)*

## Reflections (session postmortems)

- [reflections/2026-07-29-full-scope-and-slop-violation.md](reflections/2026-07-29-full-scope-and-slop-violation.md): Reflection: the full-scope claim and the ungated output channel *(status not declared)*
- [reflections/2026-07-29-what-is-going-wrong.md](reflections/2026-07-29-what-is-going-wrong.md): Reflection: why the research did not become the system *(status not declared)*
- [reflections/2026-07-30-analysis-that-never-becomes-code.md](reflections/2026-07-30-analysis-that-never-becomes-code.md): Reflection: analysis that never becomes code *(status not declared)*
- [reflections/2026-07-30-thesis-and-deck-review.md](reflections/2026-07-30-thesis-and-deck-review.md): Reflection: reviewing Yarin Beer's MSc thesis and its presentation deck *(status not declared)*
- [reflections/2026-07-30-what-i-saw.md](reflections/2026-07-30-what-i-saw.md): Reflection: everything I saw, including what I did not say at the time *(status not declared)*
- [reflections/2026-07-31-session-close-what-the-instruments-caught.md](reflections/2026-07-31-session-close-what-the-instruments-caught.md): Reflection: what the instruments caught, and what only the operator caught *(status not declared)*

## Handoffs (dated, between lanes and sessions)

- [2026-07-29-external-absorption-brief.md](2026-07-29-external-absorption-brief.md): External brief: absorb the saved-link corpus *(status not declared)*
- [HANDOFF-2026-07-27-research-transfer.md](HANDOFF-2026-07-27-research-transfer.md): Handoff: external research, and what it changes here *(status not declared)*
- [HANDOFF-2026-07-27-session-close.md](HANDOFF-2026-07-27-session-close.md): Session handoff, 2026-07-27 *(status not declared)*
- [HANDOFF-2026-07-29-absorption-session.md](HANDOFF-2026-07-29-absorption-session.md): Session handoff, 2026-07-29 evening, lane B *(status not declared)*
- [HANDOFF-2026-07-29-session-close.md](HANDOFF-2026-07-29-session-close.md): Session handoff, 2026-07-29, lane B *(status not declared)*
- [HANDOFF-2026-07-30-latent-channel-and-gastown.md](HANDOFF-2026-07-30-latent-channel-and-gastown.md): Handoff 2026-07-30: latent inter-agent channel, Gastown review loop, and two blockers *(status not declared)*
- [HANDOFF-2026-07-30-overnight-run.md](HANDOFF-2026-07-30-overnight-run.md): Handoff: overnight autonomous run, 2026-07-30 *(status not declared)*
- [HANDOFF-2026-07-30-session-close.md](HANDOFF-2026-07-30-session-close.md): Session handoff, 2026-07-29 into 2026-07-30, lane B *(status not declared)*
- [HANDOFF-2026-07-31-review-oracle-repair.md](HANDOFF-2026-07-31-review-oracle-repair.md): Handoff: review-domain oracle repair, and what the thesis job taught the harness *(status not declared)*
- [HANDOFF-2026-07-31-session-close.md](HANDOFF-2026-07-31-session-close.md): Handoff: WSL migration, review-oracle repair, and a duplicated launcher *(status not declared)*
- [HANDOFF-FROM-LEARNING-2026-07-27.md](HANDOFF-FROM-LEARNING-2026-07-27.md): Handoff to the Claude-setup session, from the learning-platform session *(status not declared)*
- [HANDOFF-FROM-LEARNING-2026-07-29.md](HANDOFF-FROM-LEARNING-2026-07-29.md): Handoff from the learning lane: discovery must watch organizations, not trending *(status not declared)*
- [HANDOFF-FROM-NEW-RECRUIT-2026-07-29.md](HANDOFF-FROM-NEW-RECRUIT-2026-07-29.md): Handoff: numerical stack preference was invisible to general sessions *(status not declared)*
- [HANDOFF-README-OWNERSHIP-2026-07-29.md](HANDOFF-README-OWNERSHIP-2026-07-29.md): Handoff to the resume engine: the GitHub profile README is yours to own *(status not declared)*
- [HANDOFF-TO-LEARNING-2026-07-27.md](HANDOFF-TO-LEARNING-2026-07-27.md): Handoff to the learning platform session, from the setup and resume session *(status not declared)*
- [HANDOFF-TO-LEARNING-2026-07-30-process-cost-and-boundaries.md](HANDOFF-TO-LEARNING-2026-07-30-process-cost-and-boundaries.md): Handoff to Lane C (learning): process cost, boundaries, and how to measure them *(status not declared)*

## Prior art

`prior-art/` holds one JSON record per component over 300 lines of Python, naming
what third-party tool could do its job. 39 records as of 2026-07-31, checked by
`python tools/map/codemap.py prior-art`. `prior-art/out-of-scope.txt` lists the
prefixes exempted and why.

## Operator input (pasted material, not authored here)

- [gemini-code-1785410845331.md](gemini-code-1785410845331.md): Refactoring the SOTA Agent Stack (July 2026) *(status not declared)*
- [gemini-code-1785455675294.md](gemini-code-1785455675294.md): MISSION SPECIFICATION: Build "nexus-engine-rs" *(status not declared)*
- [gemini-code-1785457549011.md](gemini-code-1785457549011.md): MISSION: BUILD A NEXT-GEN HYBRID RAG ENGINE (PAGEINDEX + LIGHTRAG + SPECULATIVE ROUTING) *(status not declared)*
- [gemini-code-1785458291930.md](gemini-code-1785458291930.md): gemini-code-1785458291930 *(status not declared)*
- [memory-layer--nexus-gemini-code-1785456331041.md](memory-layer--nexus-gemini-code-1785456331041.md): MISSION SPECIFICATION: Build "nexus-engine-rs" *(status not declared)*
- [prompt-research-effiefecnt-.md-files-gemini-code-1785450497712.md](prompt-research-effiefecnt-.md-files-gemini-code-1785450497712.md): Role & Purpose *(status not declared)*

## State (operational, ADR-0010 and ADR-0011)

- `../state/lessons.jsonl`: the lessons ledger, 42 rows.
- `../state/claims.jsonl`: lane claims, appended BEFORE work starts.
- `../state/claims-verify.jsonl`: 26 claims, each with a falsifier. Run `python tools/refute/refute.py run`.
- `../state/gate-runs.jsonl`, `../state/refutations.jsonl`: append-only verdict ledgers.
- `../state/bus.jsonl`: hash-chained cross-session bus. `python tools/bus/bus.py verify`.
- `../tools/selfimprove/proposals.jsonl`: ranked open work.

## TODO

- [../TODO.md](../TODO.md): the single ticket list, grouped by layer.
