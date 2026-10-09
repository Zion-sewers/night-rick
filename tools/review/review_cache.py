#!/usr/bin/env python3
"""Tiered memoized review decisions + trigger-conditioned aspect execution.

Issue #372, mechanism adapted from AIGUIDE ch.11 ("From Compute to Cost"):
the chapter memoizes planner decisions in three tiers (exact / normalized /
semantic) with context guards so a decision is never replayed under different
conditioning, and it accounts expected cost as
    expected_calls = P(triggered) x calls_when_triggered x (1 - memoized)
(Table 11-3). The same two mechanisms apply to this repo's review pipeline:
panel personas (tools/review/panel.py, deterministic check sets, cheap) and
the registry aspects (tools/review/actors.json, enacted by external actors,
expensive).

WHAT LIVES HERE
  TieredDecisionCache  exact -> normalized -> semantic lookup chain with full
                       conditioning on every key, anti-loop forced-live guard,
                       and per-tier telemetry.
  evaluate_triggers    per-aspect trigger predicates over diff signals
                       (file-type / diff-size / risk). Cheap deterministic
                       checks are the "100%" guardrails row and always run;
                       expensive aspects run only when triggered.
  expected_calls_table the Table 11-3 accounting, emitted per review so the
                       cost of the review itself is visible.

EVIDENCE LEVELS (repo convention)
  established: memoization; canonicalization before hashing; multiset Jaccard;
      trigger predicates over explicit signals.
  adaptation:  AIGUIDE ch.11 tiered decision cache + expected-calls accounting
      applied to review decisions; token-multiset similarity in place of the
      chapter's embedding similarity (no embedding dependency by design).
  unverified:  the chapter's 47% call-avoidance figure is the book's
      illustrative run, not measured here.

FAIL-CLOSED CONTRACT. Every lookup requires the full conditioning tuple to
match; any mismatch is a miss, never a replay. A cache miss costs a live run,
never a wrong verdict. The semantic tier is opt-in (disabled by default):
mis-memoized review verdicts are hallucinated approvals, which is the
chapter's own warning about too-low tau.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

# ------------------------------------------------------------------ tiers

TIER_EXACT = "exact"
TIER_NORMALIZED = "normalized"
TIER_SEMANTIC = "semantic"

CACHE_VERSION = 2
CACHE_MAX_ENTRIES = 500

# Consecutive normalized/semantic replays of one entry before the anti-loop
# guard forces a live run (ch.11 callout: replayed decisions that stop
# producing new findings across re-reviews of an evolving PR must not run
# forever). Exact-tier hits are byte-identical replays of an identical input
# and are counted, not capped.
MAX_REPLAYS = 3

# Token-multiset Jaccard threshold for the semantic tier. Deliberately high:
# a one-token change in a small diff must NOT clear it (pinned by test).
SEMANTIC_TAU = 0.95

_NO_PRIOR = "no-prior-findings"


# ------------------------------------------------------------------ keys


def canonical_key(lines: list[dict]) -> str:
    """Exact-tier key: byte-identical canonical diff.

    Sorting makes the key independent of diff order; (file, text) pairs make
    it independent of line numbers.
    """
    h = hashlib.sha256()
    for f, t in sorted((ln["file"], ln["text"]) for ln in lines):
        h.update(f.encode("utf-8"))
        h.update(b"\0")
        h.update(t.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


_WS_RUN = re.compile(r"\s+")


def _normalize_path(path: str) -> str:
    """Path normalization: one spelling per location.

    Strips a leading ./ and collapses duplicate separators. Deliberately NOT
    rename-insensitive: a renamed file is a different review subject (the
    file-type context can change), so a rename is a miss, not a reuse.
    """
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = re.sub(r"/{2,}", "/", p)
    return p


def normalized_key(lines: list[dict]) -> str:
    """Normalized-tier key: formatting-insensitive canonical diff (ch.11 Ex 11-5).

    Whitespace runs collapse to a single space and leading/trailing whitespace
    is stripped, so a reindent or reformatting reuses the prior deterministic
    verdict without re-running it. Content changes (including token changes
    inside string literals) change the key: this tier is whitespace/format
    insensitive, not content insensitive.

    KNOWN RESIDUAL, stated rather than hidden: whitespace inside a string
    literal can change program semantics (e.g. a message or a regex), and this
    tier cannot see that. The replay cap (MAX_REPLAYS) bounds how long such a
    replay can persist without a live run, and the conditioning tuple keeps
    the replay inside one file-type context. tests/test_review_cache_tiers.py
    pins both the reuse case and the content-change-miss case.
    """
    h = hashlib.sha256()
    pairs = sorted(
        (_normalize_path(ln["file"]), _WS_RUN.sub(" ", ln["text"]).strip())
        for ln in lines
    )
    for f, t in pairs:
        h.update(f.encode("utf-8"))
        h.update(b"\0")
        h.update(t.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


_TOKEN = re.compile(r"\w+")


def semantic_fingerprint(lines: list[dict]) -> dict[str, int]:
    """Change-shape fingerprint: token multiset over the added lines.

    Lowercased word tokens with counts. Compared with multiset Jaccard; only
    within one persona scope and under the full conditioning guard. This is
    the adaptation of the chapter's embedding-similarity tier: same role
    (vaguely-similar change shapes), no embedding dependency.
    """
    counts: dict[str, int] = {}
    for ln in lines:
        for tok in _TOKEN.findall(ln["text"].lower()):
            counts[tok] = counts.get(tok, 0) + 1
    return counts


def jaccard_multiset(a: dict[str, int], b: dict[str, int]) -> float:
    """Multiset Jaccard: sum(min)/sum(max) over token counts."""
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return inter / union if union else 1.0


# ------------------------------------------------------------------ conditioning


def conditioning_fingerprint(*, registry_fp: str, langs: list[str],
                             external_mode: str, prior_checksum: str) -> str:
    """Full conditioning on the key (ch.11 Ex 11-3 warning).

    A decision is never replayed under different conditioning. The tuple is:
      (canonical diff key, check-registry fingerprint, file-type context,
       external-backend mode, prior findings on the PR).
    A cached PASS from an older check-set version cannot replay under a newer
    one (fingerprint in the key); a local-only verdict cannot replay under an
    external run (mode in the key); a verdict reached with different prior
    findings cannot replay (prior checksum in the key).
    """
    payload = {
        "registry_fp": registry_fp,
        "langs": sorted(langs),
        "external_mode": external_mode,
        "prior_checksum": prior_checksum,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def prior_findings_checksum(project: str, base: str,
                            exclude_sha: str | None = None) -> str:
    """Checksum of the prior review's findings for this base, if any.

    Scans <project>/state/reviews/*.json for the latest artifact with a
    matching base and checksums its canonical findings
    (persona, check, file, line, severity). Artifacts for `exclude_sha`
    (the commit currently being reviewed) are skipped: a re-run of the
    same commit must see the same prior conditioning as the run that
    stored the entry, otherwise every run would invalidate the next and
    the exact tier could never hit twice in a row. No artifact ->
    the NO_PRIOR constant, so first reviews share one conditioning
    instead of each inventing a different "none".
    """
    review_dir = os.path.join(project, "state", "reviews")
    best = None
    try:
        names = os.listdir(review_dir)
    except OSError:
        names = []
    for name in sorted(names):
        if not name.endswith(".json") or name == "decision-cache.json":
            continue
        if exclude_sha is not None and name == exclude_sha + ".json":
            continue
        try:
            with open(os.path.join(review_dir, name), encoding="utf-8") as fh:
                art = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(art, dict) or art.get("base") != base:
            continue
        stamp = str(art.get("reviewed_at", "")) + name
        if best is None or stamp > best[0]:
            best = (stamp, art)
    if best is None:
        return hashlib.sha256(_NO_PRIOR.encode("utf-8")).hexdigest()
    canon = sorted(
        (str(f.get("persona", "")), str(f.get("check", "")),
         str(f.get("file", "")), str(f.get("line", "")),
         str(f.get("severity", "")))
        for f in best[1].get("findings", []) if isinstance(f, dict)
    )
    return hashlib.sha256(json.dumps(canon).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ the cache


class TieredDecisionCache:
    """Persistent tiered decision cache for panel verdicts (issue #372).

    Lookup order: exact -> normalized -> semantic (opt-in). Every tier
    requires the full conditioning tuple to match. Normalized/semantic hits
    increment the entry's replay counter; at MAX_REPLAYS the anti-loop guard
    forces a live run instead of replaying. Telemetry (hits per tier,
    forced-live counts, stores, misses) is accumulated per process and
    exposed for the review artifact.
    """

    def __init__(self, path: str):
        self.path = path
        self._data: dict = self._load()
        self.telemetry: dict[str, int] = {
            "exact_hits": 0, "normalized_hits": 0, "semantic_hits": 0,
            "misses": 0, "forced_live": 0, "stores": 0,
        }

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
                entries = data.get("entries", {})
                if isinstance(entries, dict):
                    return entries
        except (OSError, ValueError):
            pass
        return {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"version": CACHE_VERSION, "entries": self._data},
                          fh, indent=1)
        except OSError:
            pass

    def _conditioned(self, entry: dict, cond: str) -> bool:
        return isinstance(entry, dict) and entry.get("conditioning") == cond

    def lookup(self, lines: list[dict], *, registry_fp: str,
               langs: list[str] | None = None,
               external_mode: str = "local-only",
               prior_checksum: str | None = None,
               semantic_enabled: bool = False,
               persona_scope: str | None = None) -> dict:
        """Look up a memoized decision.

        Returns a result dict: {"tier": tier|None, "entry": entry|None,
        "forced_live": bool, "forced_key": key|None}. forced_live means the
        anti-loop guard fired: the caller MUST run the checks live and store
        the fresh verdict, passing forced_key as store()'s
        reset_replays_for_key so the capped entry's replay counter resets.
        Without the reset the guard degrades to a one-way ratchet: the
        capped entry would force live on every future variant forever.
        """
        cond = conditioning_fingerprint(
            registry_fp=registry_fp,
            langs=list(langs or []),
            external_mode=external_mode,
            prior_checksum=prior_checksum or hashlib.sha256(
                _NO_PRIOR.encode("utf-8")).hexdigest(),
        )
        ekey = canonical_key(lines)

        ent = self._data.get(ekey)
        if self._conditioned(ent, cond):
            ent["hits"] = int(ent.get("hits", 0)) + 1
            self.telemetry["exact_hits"] += 1
            self._save()
            return {"tier": TIER_EXACT, "entry": ent, "forced_live": False,
                    "forced_key": None}

        nkey = normalized_key(lines)
        for key, cand in self._data.items():
            if not isinstance(cand, dict) or cand.get("normalized_key") != nkey:
                continue
            if not self._conditioned(cand, cond):
                continue
            if int(cand.get("replays", 0)) >= MAX_REPLAYS:
                self.telemetry["forced_live"] += 1
                return {"tier": None, "entry": cand, "forced_live": True,
                        "forced_key": key}
            cand["replays"] = int(cand.get("replays", 0)) + 1
            cand["hits"] = int(cand.get("hits", 0)) + 1
            self.telemetry["normalized_hits"] += 1
            self._save()
            return {"tier": TIER_NORMALIZED, "entry": cand, "forced_live": False}

        if semantic_enabled:
            sfp = semantic_fingerprint(lines)
            for key, cand in self._data.items():
                if not isinstance(cand, dict):
                    continue
                if cand.get("persona_scope") != persona_scope:
                    continue
                if not self._conditioned(cand, cond):
                    continue
                stored = cand.get("semantic_fp") or {}
                if jaccard_multiset(sfp, stored) < SEMANTIC_TAU:
                    continue
                if int(cand.get("replays", 0)) >= MAX_REPLAYS:
                    self.telemetry["forced_live"] += 1
                    return {"tier": None, "entry": cand, "forced_live": True,
                            "forced_key": key}
                cand["replays"] = int(cand.get("replays", 0)) + 1
                cand["hits"] = int(cand.get("hits", 0)) + 1
                self.telemetry["semantic_hits"] += 1
                self._save()
                return {"tier": TIER_SEMANTIC, "entry": cand,
                        "forced_live": False}

        self.telemetry["misses"] += 1
        return {"tier": None, "entry": None, "forced_live": False}

    def store(self, lines: list[dict], *, registry_fp: str,
              langs: list[str] | None = None,
              external_mode: str = "local-only",
              prior_checksum: str | None = None,
              verdict: str, findings: list[dict],
              persona_scope: str | None = None,
              reset_replays_for_key: str | None = None) -> None:
        """Store a live verdict.

        Storing resets the new entry's replay counter (a live run happened).
        reset_replays_for_key also resets the named entry's counter: pass
        lookup()'s forced_key after a forced live run, so the capped entry's
        replay budget renews instead of ratcheting shut forever.
        """
        cond = conditioning_fingerprint(
            registry_fp=registry_fp,
            langs=list(langs or []),
            external_mode=external_mode,
            prior_checksum=prior_checksum or hashlib.sha256(
                _NO_PRIOR.encode("utf-8")).hexdigest(),
        )
        if len(self._data) >= CACHE_MAX_ENTRIES:
            oldest = min(self._data,
                         key=lambda k: self._data[k].get("ts", 0)
                         if isinstance(self._data[k], dict) else 0)
            del self._data[oldest]
        self._data[canonical_key(lines)] = {
            "registry_fp": registry_fp,
            "conditioning": cond,
            "langs": sorted(langs or []),
            "external_mode": external_mode,
            "prior_checksum": prior_checksum,
            "verdict": verdict,
            "findings": findings,
            "ts": time.time(),
            "replays": 0,
            "hits": 0,
            "normalized_key": normalized_key(lines),
            "semantic_fp": semantic_fingerprint(lines),
            "persona_scope": persona_scope,
        }
        if reset_replays_for_key is not None:
            capped = self._data.get(reset_replays_for_key)
            if isinstance(capped, dict):
                capped["replays"] = 0
        self.telemetry["stores"] += 1
        self._save()

    def telemetry_snapshot(self) -> dict[str, int]:
        return dict(self.telemetry)


# ------------------------------------------------------------------ triggers
#
# Trigger-conditioned aspect execution (ch.11 Table 11-3). Cheap deterministic
# checks are the "100%" guardrails row: they always run. Expensive aspects
# (enacted by external actors per tools/review/actors.json) run only when a
# trigger fires. Triggers are explicit, few, and named so a skipped aspect is
# attributable, never silent.
#
# STATED RESIDUALS.
# - --allow-external no longer guarantees the external leg. When no aspect
#   trigger fires, the leg is skipped and the skip is recorded in the
#   artifact's external_note (never silent), but the coverage narrows vs
#   the previous always-run behavior: a YAML/CI-only diff with no code
#   signals gets no model pass. This is the issue's demanded mechanism,
#   not an accident, and it is stated here so the narrowing is a choice.
# - persona_scope=None means panel-wide. Per-persona scoping exists as a
#   conditioning dimension for future per-persona verdict stores; the
#   semantic tier's scope isolation is exercised by tests, inert in
#   panel.py's wiring today.
# - external_mode is a live conditioning dimension even though the current
#   wiring bypasses the cache for external runs: a local-only verdict can
#   never replay under an external run, by construction rather than by
#   the bypass alone.
# - Replayed findings carry the line numbers of the run that stored them;
#   the keys ignore line numbers by design, so a reformatted re-review
#   replays findings against shifted lines. Findings cite file+check as
#   well as line, which survive reformatting; the line is advisory.

CODE_LANGS = {"py", "ts", "js", "go", "rs", "java", "kt", "cs", "rb", "php",
              "sql", "sh", "ps1", "swift"}
UX_LANGS = {"ts", "js", "html", "css"}
IO_LANGS = {"py", "ts", "js", "go"}  # IO edges: where boundary checks bite

# Registry aspects in actors.json order.
ASPECTS = ["correctness", "security", "boundary", "simplicity",
           "perf", "slop", "tests", "a11y"]


def review_signals(lines: list[dict], findings: list[dict],
                   langs_of: dict[str, str]) -> dict:
    """Diff signals the triggers read. `langs_of` maps file -> language tag
    (panel.lang_of); kept as a parameter so this module never imports panel."""
    langs = {langs_of.get(ln["file"], "") for ln in lines}
    langs.discard("")
    files = {ln["file"] for ln in lines}
    n_code = sum(1 for ln in lines if langs_of.get(ln["file"]) in CODE_LANGS)
    high_by_persona: dict[str, bool] = {}
    for f in findings:
        if isinstance(f, dict) and f.get("severity") == "high":
            high_by_persona[str(f.get("persona", ""))] = True
    return {
        "langs": sorted(langs),
        "n_lines": len(lines),
        "n_code_lines": n_code,
        "has_test_file": any(re.search(r"(^|/)(test_.*|.*_test\.[a-z]+|tests/)", f)
                             for f in files),
        "has_prose": any(f.lower().endswith((".md", ".markdown", ".rst", ".txt"))
                         for f in files),
        "high_by_persona": high_by_persona,
    }


def evaluate_triggers(signals: dict) -> dict[str, dict]:
    """Per-aspect trigger evaluation. Returns aspect -> {"triggered", "trigger"}.

    A trigger is a named signal; an aspect with no fired trigger does not run
    its expensive enactment this review. The names are the audit trail.
    """
    langs = set(signals.get("langs", []))
    n = int(signals.get("n_lines", 0))
    n_code = int(signals.get("n_code_lines", 0))
    has_code = bool(langs & CODE_LANGS)
    high = signals.get("high_by_persona", {}) or {}

    def trig(name: str, fired: bool) -> dict:
        return {"triggered": bool(fired), "trigger": name if fired else None}

    return {
        # File-type signal: code changed. Risk signal: the cheap pass already
        # found a HIGH in this dimension, so the expensive pass is warranted
        # even where the file-type signal alone would not fire it.
        "correctness": trig("file-type:code", has_code) if not high.get("correctness")
        else {"triggered": True, "trigger": "risk:high-correctness-finding"},
        "security": trig("file-type:code", has_code) if not high.get("security")
        else {"triggered": True, "trigger": "risk:high-security-finding"},
        "boundary": trig("file-type:io-edge", bool(langs & IO_LANGS)),
        # Diff-size signals: large changes earn the expensive reads.
        "simplicity": trig("diff-size>=100", n >= 100),
        "perf": trig("diff-size>=20-code-lines", n_code >= 20),
        "slop": trig("file-type:prose", signals.get("has_prose", False))
        if not n >= 200 else {"triggered": True, "trigger": "diff-size>=200"},
        # Test-gap signal: code added with no test in the diff.
        "tests": ({"triggered": True, "trigger": "test-gap:code-without-test"}
                  if has_code and not signals.get("has_test_file", False)
                  else trig("none", False)),
        "a11y": trig("file-type:ux-surface", bool(langs & UX_LANGS)),
    }


def external_should_run(trigger_eval: dict[str, dict]) -> bool:
    """The external model pass (the expensive leg) runs iff at least one
    aspect is triggered. A quiet change gets the cheap pass only, and the
    skip is recorded in the artifact note rather than silent."""
    return any(v.get("triggered") for v in trigger_eval.values())


def expected_calls_table(trigger_eval: dict[str, dict], *,
                         external_possible: bool,
                         external_ran: bool,
                         local_ran: bool,
                         memoized_fraction: float) -> list[dict]:
    """Table 11-3 accounting per review, at executed-leg granularity.

    expected_calls = P(triggered) x calls_when_triggered x (1 - memoized).
    P(triggered) is THIS review's trigger outcome (1/0 with the named
    trigger); across many reviews the mean of the column estimates the
    chapter's probability. actual_calls is MEASURED, never derived: the
    local leg ran or it did not, the external leg ran or it did not.

    Rows are execution legs, not aspects, because the execution is leg-
    shaped: the cheap deterministic panel is one leg, the external model
    pass is one leg covering whichever aspects triggered. Per-aspect
    trigger detail lives in aspect_triggers (evaluate_triggers output),
    which this table does not duplicate. An earlier revision put
    per-aspect call counts in this table while the wiring gated one
    boolean for the whole leg; the table then claimed reviews that never
    ran. Leg granularity keeps the accounting and the execution identical.
    """
    fired = sorted(t["trigger"] for t in trigger_eval.values()
                   if t.get("triggered") and t.get("trigger"))
    ext_p = 1.0 if (external_possible and fired) else 0.0
    return [
        {
            "leg": "guardrails(local-panel)",
            "p_triggered": 1.0,
            "trigger": "always",
            "calls_when_triggered": 1,
            "memoized": memoized_fraction,
            "expected_calls": round(1.0 * 1 * (1 - memoized_fraction), 3),
            "actual_calls": 1 if local_ran else 0,
        },
        {
            "leg": "external(model-leg)",
            "p_triggered": ext_p,
            "trigger": ("any-aspect:" + ",".join(fired)) if fired else None,
            "calls_when_triggered": 1,
            "memoized": 0.0,
            "expected_calls": round(ext_p * 1 * (1 - 0.0), 3),
            "actual_calls": 1 if external_ran else 0,
        },
    ]
