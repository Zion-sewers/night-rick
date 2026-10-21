#!/usr/bin/env python3
"""E-row enforcement checks for the book-to-standard pipeline.

Composite (diff-level) review checks that do not fit the per-line pattern
shape of PERSONAS in panel.py. Every function here is pure: added lines in,
findings out. The wiring lives in panel.run_local / panel.cmd_run; this
module never imports panel, so there is no import cycle.

E-row index:
  E-0001  undeclared tradeoff fails the panel        (issue #374)
  E-0002  high-risk prompt/schema/example edits need
          a declared regression scope                (issue #373)
  E-0003  memoized review decisions, fingerprint-
          guarded keys, anti-stale expiry            (issue #372)

Conventions shared with panel.py: findings carry persona/check/severity/
file/line/why/snippet/source. Severity constants mirror panel.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

HIGH = "high"
MED = "medium"
LOW = "low"


def _is_code(path: str) -> bool:
    """Trigger patterns scan code, not prose. A document that SHOWS a
    guard being disabled is demonstrating, not doing; panel.py already
    excludes md from pattern checks for the same reason."""
    return not path.lower().endswith((".md", ".markdown", ".rst", ".txt"))


# ------------------------------------------------------------------ E-0001
# Undeclared tradeoff fails the panel (issue #374).
#
# Mechanism: a diff that weakens a guard (safety axis regresses) while
# tuning throughput/cost (another axis improves) must declare the tradeoff
# in the diff itself, or the review fails. The declaration is a `tradeoff:`
# record naming a measured budget, e.g.
#   tradeoff: accepts +80ms p95 for a stricter identity check
# The panel cannot measure the axes the way a benchmark can; the
# implementable core is the co-occurrence of guard-weakening and
# perf/cost-tuning shapes without a declaration. Either shape alone is
# not a finding: tuning perf without touching guards is ordinary work,
# and touching a guard alone is already covered by the persona checks.

_GUARD_WEAKENING = [
    r"verify\s*=\s*False",
    r"rejectUnauthorized\s*:\s*false",
    r"InsecureSkipVerify\s*:\s*true",
    r"NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0",
    r"#\s*nosec\b",
    r"\bauth(?:entication)?\s*=\s*False\b",
    r"check_signature\s*=\s*False",
    r"verify_signature['\"]?\s*:\s*False",
]

_PERF_COST = [
    r"functools\.(?:lru_cache|cache)\b",
    r"@lru_cache\b",
    r"@cache\b",
    r"memoiz",
    r"concurrent\.futures",
    r"ThreadPool(?:Executor)?|ProcessPool(?:Executor)?",
    r"asyncio\.",
    r"multiprocessing",
    r"\bbatch_size\b",
    r"\bbulk_",
]

_TRADEOFF_RECORD = re.compile(r"(?i)tradeoff\s*:")


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


_GUARD_RX = _compile(_GUARD_WEAKENING)
_PERF_RX = _compile(_PERF_COST)


def check_undeclared_tradeoff(lines: list[dict]) -> list[dict]:
    """E-0001. Fires when a diff weakens a guard AND tunes perf/cost with
    no `tradeoff:` record in the added lines."""
    code_lines = [ln for ln in lines if _is_code(ln["file"])]
    weakens = [ln for ln in code_lines
               if any(rx.search(ln["text"]) for rx in _GUARD_RX)]
    tunes = [ln for ln in code_lines
             if any(rx.search(ln["text"]) for rx in _PERF_RX)]
    if not weakens or not tunes:
        return []
    if any(_TRADEOFF_RECORD.search(ln["text"]) for ln in lines):
        return []
    anchor = weakens[0]
    return [{
        "persona": "ops_release",
        "check": "undeclared-tradeoff",
        "severity": HIGH,
        "file": anchor["file"],
        "line": anchor["line"],
        "why": ("this diff weakens a guard while tuning throughput/cost and "
                "declares no tradeoff: one axis improves while another "
                "regresses with no measured budget named. Add a "
                "`tradeoff:` record (what improved, what regressed, the "
                "measured cost) or split the change."),
        "snippet": anchor["text"].strip()[:160],
        "source": "local",
    }]


# ------------------------------------------------------------------ E-0002
# High-risk prompt/schema/example edits need a declared regression scope
# (issue #373).
#
# Mechanism: not all prompt and contract edits are equal. Schema-structure
# edits, attention-directive edits, and evidence-format edits are HIGH risk:
# they change what the model attends to or what the gate reads, and the
# failure looks like missing data rather than a model error. A HIGH-risk
# edit ships only with a declared regression scope (`regression-scope:` in
# the diff) or a test added in the same diff. Example-set swaps are MEDIUM.

_PROMPT_PATH = re.compile(r"(?i)(^|/)(prompts?|templates?)/|\.prompt\.[a-z]+$|prompt", )
_SCHEMA_PATH = re.compile(r"(?i)schema|contract|openapi|jsonschema")
_EXAMPLE_PATH = re.compile(r"(?i)example")
_EVIDENCE_PATH = re.compile(r"(?i)evidence|citation")

_SCHEMA_STRUCTURE = re.compile(
    r'"(?:required|properties|enum|additionalProperties|oneOf|anyOf|allOf)"')
_ATTENTION_DIRECTIVE = re.compile(
    r"(?i)\b(bounding.?box|region.?of.?interest|focus on|zoom (in|to)|"
    r"ignore (the|all)|attention (map|mask|weights))\b")
_EVIDENCE_FORMAT = re.compile(
    r"(?i)(confidence|citation|coordinate).{0,40}(format|field|schema|represent)")
_SAMPLING_PARAM = re.compile(
    r"(?i)\b(temperature|top_?p|top_?k|max_?tokens)\b\s*[:=]")

_REGRESSION_SCOPE = re.compile(r"(?i)regression.?scope\s*:")
_TEST_FILE = re.compile(r"(^|/)(test_.*|.*_test\.[a-z]+|tests/)")


def _risk_of(path: str, text: str) -> str | None:
    """Risk class for one added line, or None if the file is out of scope."""
    low = path.lower()
    is_prompt = bool(_PROMPT_PATH.search(low))
    is_schema = bool(_SCHEMA_PATH.search(low))
    is_example = bool(_EXAMPLE_PATH.search(low))
    is_evidence = bool(_EVIDENCE_PATH.search(low))
    if not (is_prompt or is_schema or is_example or is_evidence):
        return None
    if is_schema and _SCHEMA_STRUCTURE.search(text):
        return HIGH
    if is_prompt and _ATTENTION_DIRECTIVE.search(text):
        return HIGH
    if is_evidence and _EVIDENCE_FORMAT.search(text):
        return HIGH
    if is_prompt and _SAMPLING_PARAM.search(text):
        return MED
    return None


def check_edit_risk(lines: list[dict], all_lines: list[dict] | None = None) -> list[dict]:
    """E-0002. HIGH-risk prompt/schema/evidence edits without a declared
    regression scope (and no test in the diff) fail the panel.

    Triggers scan `lines` (reviewable lines only). Satisfaction looks at
    `all_lines`: a test added under tests/ is exempt from review, but it
    still counts as the regression evidence the row demands."""
    scope_lines = all_lines if all_lines is not None else lines
    files = sorted({ln["file"] for ln in scope_lines})
    has_scope = any(_REGRESSION_SCOPE.search(ln["text"]) for ln in scope_lines)
    has_test = any(_TEST_FILE.search(f) for f in files)
    if has_scope or has_test:
        return []
    findings = []
    seen: set[str] = set()
    for ln in lines:
        risk = _risk_of(ln["file"], ln["text"])
        if risk != HIGH or ln["file"] in seen:
            continue
        seen.add(ln["file"])
        findings.append({
            "persona": "correctness",
            "check": "high-risk-edit-no-regression-scope",
            "severity": MED,
            "file": ln["file"],
            "line": ln["line"],
            "why": ("a high-risk prompt/schema/evidence edit (schema "
                    "structure, attention directive, or evidence format) "
                    "with no declared regression scope: the failure mode "
                    "looks like missing data, not a model error, so it "
                    "ships only with a `regression-scope:` record or a "
                    "test in the same diff."),
            "snippet": ln["text"].strip()[:160],
            "source": "local",
        })
    return findings


def composite_findings(reviewable: list[dict],
                      all_lines: list[dict] | None = None) -> list[dict]:
    """All diff-level E-row checks. Called from panel.run_local after the
    per-line persona checks. `reviewable` carries the exemption filtering;
    `all_lines` (unfiltered) is used for satisfaction evidence such as
    tests added under tests/."""
    if all_lines is None:
        all_lines = reviewable
    return (check_undeclared_tradeoff(reviewable)
            + check_edit_risk(reviewable, all_lines))


# ------------------------------------------------------------------ E-0003
# Memoized review decisions, fingerprint-guarded keys, anti-stale expiry
# (issue #372).
#
# Mechanism: a panel verdict on a diff is reusable when the same
# canonicalized diff recurs — but only under identical conditioning. The
# cache key is the canonical diff plus a fingerprint of the check
# registry; any registry change (new/edited check) expires old entries,
# so a PASS from an older check set never replays under a newer one.
# Exact tier only: byte-identical canonical diff. The normalized and
# semantic tiers, and trigger-conditioned aspect execution, are tracked
# follow-ups, not this row.

CACHE_VERSION = 1
CACHE_MAX_ENTRIES = 500


def registry_fingerprint(personas: dict) -> str:
    """Fingerprint of the check registry: (persona, check id, severity,
    pattern) sorted. Any check added, removed, or edited changes it.

    AST checks (tools/review/async_purity.py) do not live in the PERSONAS
    pattern tuples, so the check's behavior hash is appended explicitly:
    editing its blocking tables expires memoized decisions exactly like a
    pattern edit does.
    """
    items = sorted(
        (persona, cid, sev, pat)
        for persona, spec in personas.items()
        for cid, sev, _langs, pat, _why in spec["checks"]
    )
    try:
        from async_purity import config_fingerprint
        ast_fp = config_fingerprint()
    except Exception:
        ast_fp = "unavailable"
    items.append(("correctness", "async-purity", "medium",
                  "ast:blocking-sync-call-in-async-def:" + ast_fp))
    return hashlib.sha256(json.dumps(items).encode("utf-8")).hexdigest()


def canonical_key(lines: list[dict]) -> str:
    """Exact-tier key: byte-identical canonical diff. Sorting makes the
    key independent of diff order; file+text pairs make it independent
    of line numbers."""
    h = hashlib.sha256()
    for f, t in sorted((ln["file"], ln["text"]) for ln in lines):
        h.update(f.encode("utf-8"))
        h.update(b"\0")
        h.update(t.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


class ReviewDecisionCache:
    """Persistent exact-tier decision cache for panel verdicts."""

    def __init__(self, path: str):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
                return data.get("entries", {})
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

    def lookup(self, lines: list[dict], fingerprint: str) -> dict | None:
        """A hit requires the entry's fingerprint to match the current
        registry: a stale entry is a miss, never a replay."""
        ent = self._data.get(canonical_key(lines))
        if not ent or ent.get("fingerprint") != fingerprint:
            return None
        return ent

    def store(self, lines: list[dict], fingerprint: str,
              verdict: str, findings: list[dict]) -> None:
        if len(self._data) >= CACHE_MAX_ENTRIES:
            oldest = min(self._data, key=lambda k: self._data[k].get("ts", 0))
            del self._data[oldest]
        self._data[canonical_key(lines)] = {
            "fingerprint": fingerprint,
            "verdict": verdict,
            "findings": findings,
            "ts": time.time(),
        }
        self._save()
