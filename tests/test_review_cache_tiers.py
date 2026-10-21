"""Tiered review-decision cache + trigger-conditioned aspects (issue #372).

Every behavior ships with a running adversarial test: each tier's reuse is
proven, and each tier's refusal to reuse is proven against the case that
would make reuse dangerous (mis-memoized verdicts are hallucinated
approvals). Conventions follow tests/test_erows.py: tools/review on
sys.path, panel.added_lines over a temp repo for the integration half.
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "review"))
import panel  # noqa: E402
import e_rows  # noqa: E402
import review_cache as rc  # noqa: E402


def _sh(cmd, cwd):
    import subprocess
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                       text=True, timeout=60)
    assert p.returncode == 0, p.stderr


def _diff(files: dict[str, str]):
    """Temp git repo whose HEAD diff adds `files`; return added lines."""
    td = tempfile.mkdtemp()
    _sh("git init -q .", td)
    _sh("git -c user.email=t@t -c user.name=t commit -q --allow-empty -m base", td)
    for name, body in files.items():
        full = os.path.join(td, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body if body.endswith("\n") else body + "\n")
    return panel.added_lines(td, "HEAD")


def _cache(tmp_path):
    return rc.TieredDecisionCache(str(tmp_path / "decision-cache.json"))


_FP = "fp-test-registry"
_LANGS = ["py"]
_COND = {"registry_fp": _FP, "langs": _LANGS, "external_mode": "local-only",
         "prior_checksum": None}


def _lookup(c, lines, **kw):
    args = dict(_COND)
    args.update(kw)
    return c.lookup(lines, **args)


def _store(c, lines, verdict="pass", findings=None, **kw):
    args = dict(_COND)
    args.update(kw)
    c.store(lines, verdict=verdict, findings=findings or [], **args)

def _lines(file="a.py", texts=("x = 1",)):
    return [{"file": file, "line": i + 1, "text": t}
            for i, t in enumerate(texts)]


def _finding_checksum(findings):
    canon = sorted(
        (str(f.get("persona", "")), str(f.get("check", "")),
         str(f.get("file", "")), str(f.get("line", "")),
         str(f.get("severity", "")))
        for f in findings)
    return hashlib.sha256(json.dumps(canon).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ exact tier

def test_exact_rerun_served_with_identical_findings(tmp_path):
    # Acceptance: re-running review on an unchanged PR is served from cache
    # (exact tier) with identical findings; checksum proves equivalence.
    lines = _diff({"svc/app.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n"})
    findings = panel.run_local(lines)
    assert findings, "fixture must produce a finding"
    c = _cache(tmp_path)
    assert _lookup(c, lines)["tier"] is None
    _store(c, lines, verdict="changes-requested", findings=findings)
    res = _lookup(c, lines)
    assert res["tier"] == rc.TIER_EXACT
    assert res["forced_live"] is False
    assert _finding_checksum(res["entry"]["findings"]) == _finding_checksum(findings)


def test_exact_content_change_is_a_miss(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(texts=("x = 1",)))
    assert _lookup(c, _lines(texts=("x = 2",)))["tier"] is None


def test_exact_line_numbers_do_not_matter(tmp_path):
    c = _cache(tmp_path)
    _store(c, [{"file": "a.py", "line": 10, "text": "x = 1"}])
    res = _lookup(c, [{"file": "a.py", "line": 99, "text": "x = 1"}])
    assert res["tier"] == rc.TIER_EXACT


# ------------------------------------------------------------------ normalized tier

def test_normalized_formatting_only_change_reuses(tmp_path):
    # Acceptance: a formatting-only change reuses prior deterministic
    # verdicts without re-running them.
    c = _cache(tmp_path)
    _store(c, _lines(texts=("def f():", "    return 1")))
    reformatted = _lines(texts=("def  f():  ", "\treturn 1  "))
    # Exact tier must NOT hit: the bytes differ.
    assert rc.canonical_key(reformatted) != rc.canonical_key(
        _lines(texts=("def f():", "    return 1")))
    # Normalized tier hits: same shape after whitespace canonicalization.
    assert rc.normalized_key(reformatted) == rc.normalized_key(
        _lines(texts=("def f():", "    return 1")))
    res = _lookup(c, reformatted)
    assert res["tier"] == rc.TIER_NORMALIZED
    assert res["forced_live"] is False


def test_normalized_content_change_is_a_miss(tmp_path):
    # ADVERSARIAL: shell=True -> shell=False is a token change, not a
    # formatting change. Reusing the verdict would be a hallucinated
    # approval of a fixed (or broken) line.
    c = _cache(tmp_path)
    _store(c, _lines(texts=("subprocess.run(cmd, shell=True)",)))
    res = _lookup(c, _lines(texts=("subprocess.run(cmd, shell=False)",)))
    assert res["tier"] is None
    assert res["forced_live"] is False


def test_normalized_path_spelling_reuses(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(file="./a.py", texts=("x = 1",)))
    res = _lookup(c, _lines(file="a.py", texts=("x = 1",)))
    assert res["tier"] in (rc.TIER_EXACT, rc.TIER_NORMALIZED)


def test_normalized_rename_is_a_miss(tmp_path):
    # ADVERSARIAL: a renamed file is a different review subject; the
    # file-type context may have changed. Reuse across renames is refused.
    c = _cache(tmp_path)
    _store(c, _lines(file="a.py", texts=("x = 1",)))
    res = _lookup(c, _lines(file="b.py", texts=("x = 1",)))
    assert res["tier"] is None


# ------------------------------------------------------------------ conditioning

def test_conditioning_registry_change_is_a_miss(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines())
    assert _lookup(c, _lines(), registry_fp="different-fp")["tier"] is None


def test_conditioning_file_type_change_is_a_miss(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(), langs=["py"])
    assert _lookup(c, _lines(), langs=["js"])["tier"] is None


def test_conditioning_external_mode_change_is_a_miss(tmp_path):
    # ADVERSARIAL: a local-only verdict must never replay under an
    # external run; the conditioning is different.
    c = _cache(tmp_path)
    _store(c, _lines(), external_mode="local-only")
    res = _lookup(c, _lines(), external_mode="external:auto")
    assert res["tier"] is None


def test_conditioning_prior_findings_change_is_a_miss(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(), prior_checksum="abc")
    assert _lookup(c, _lines(), prior_checksum="def")["tier"] is None


def test_conditioning_tampered_entry_is_a_miss(tmp_path):
    # ADVERSARIAL: editing the cache file to transplant conditioning does
    # not produce a replay; the digest is recomputed from the live inputs.
    c = _cache(tmp_path)
    _store(c, _lines())
    p = tmp_path / "decision-cache.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    for ent in data["entries"].values():
        ent["conditioning"] = "forged"
    p.write_text(json.dumps(data), encoding="utf-8")
    c2 = _cache(tmp_path)
    assert _lookup(c2, _lines())["tier"] is None


# ------------------------------------------------------------------ anti-loop

def test_anti_loop_forces_live_after_max_replays(tmp_path):
    c = _cache(tmp_path)
    base = _lines(texts=("def f():", "    return 1"))
    _store(c, base)
    reformatted = _lines(texts=("def  f():", "\treturn 1"))
    for _ in range(rc.MAX_REPLAYS):
        res = _lookup(c, reformatted)
        assert res["tier"] == rc.TIER_NORMALIZED
        assert res["forced_live"] is False
    res = _lookup(c, reformatted)
    assert res["tier"] is None
    assert res["forced_live"] is True
    assert c.telemetry_snapshot()["forced_live"] == 1


def test_anti_loop_live_run_resets_replay_counter(tmp_path):
    # The real wiring: the forced live run stores the CURRENT (reformatted)
    # diff and passes the capped entry's forced_key, so the capped entry's
    # replay budget renews instead of ratcheting shut forever.
    c = _cache(tmp_path)
    base = _lines(texts=("def f():", "    return 1"))
    _store(c, base)
    reformatted = _lines(texts=("def  f():", "\treturn 1"))
    forced_key = None
    for _ in range(rc.MAX_REPLAYS + 1):
        res = _lookup(c, reformatted)
        if res["forced_live"]:
            forced_key = res["forced_key"]
    assert forced_key is not None
    _store(c, reformatted, reset_replays_for_key=forced_key)
    # A further formatting variant reuses via the normalized tier again:
    # the capped entry's budget was renewed.
    v2 = _lines(texts=("def   f():", " \t return 1"))
    res = _lookup(c, v2)
    assert res["tier"] == rc.TIER_NORMALIZED
    assert res["forced_live"] is False


def test_anti_loop_without_reset_key_ratchets(tmp_path):
    # Pin the failure mode the reset exists to prevent: if the caller
    # ignores forced_key, the capped entry keeps forcing live forever.
    c = _cache(tmp_path)
    base = _lines(texts=("def f():", "    return 1"))
    _store(c, base)
    reformatted = _lines(texts=("def  f():", "\treturn 1"))
    for _ in range(rc.MAX_REPLAYS + 1):
        _lookup(c, reformatted)
    _store(c, reformatted)  # no reset_replays_for_key
    res = _lookup(c, _lines(texts=("def   f():", " \t return 1")))
    assert res["forced_live"] is True


def test_exact_hits_are_counted_not_capped(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines())
    for _ in range(rc.MAX_REPLAYS + 2):
        res = _lookup(c, _lines())
        assert res["tier"] == rc.TIER_EXACT
    assert c.telemetry_snapshot()["exact_hits"] == rc.MAX_REPLAYS + 2
    assert c.telemetry_snapshot()["forced_live"] == 0


# ------------------------------------------------------------------ semantic tier

def test_semantic_disabled_by_default(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(texts=("alpha beta gamma",)))
    res = _lookup(c, _lines(texts=("gamma beta alpha",)))
    assert res["tier"] is None  # not even the semantic tier is consulted


def test_semantic_opt_in_reuses_same_shape(tmp_path):
    c = _cache(tmp_path)
    _store(c, _lines(texts=("alpha beta gamma",)), persona_scope="security")
    res = _lookup(c, _lines(texts=("gamma beta alpha",)),
                  semantic_enabled=True, persona_scope="security")
    assert res["tier"] == rc.TIER_SEMANTIC


def test_semantic_scope_isolation(tmp_path):
    # ADVERSARIAL: the semantic tier reuses only within the same persona
    # scope; a cross-scope replay is refused.
    c = _cache(tmp_path)
    _store(c, _lines(texts=("alpha beta gamma",)), persona_scope="security")
    res = _lookup(c, _lines(texts=("gamma beta alpha",)),
                  semantic_enabled=True, persona_scope="correctness")
    assert res["tier"] is None


def test_semantic_one_token_change_in_small_diff_misses(tmp_path):
    # ADVERSARIAL: Jaccard 2/4 = 0.5 < tau 0.95. A near-miss change in a
    # small diff must not clear the threshold.
    c = _cache(tmp_path)
    _store(c, _lines(texts=("alpha beta gamma",)), persona_scope="security")
    res = _lookup(c, _lines(texts=("alpha beta delta",)),
                  semantic_enabled=True, persona_scope="security")
    assert res["tier"] is None


def test_semantic_jaccard_math():
    a = {"x": 2, "y": 1}
    b = {"x": 1, "y": 1, "z": 1}
    # min: x=1,y=1,z=0 -> 2 ; max: x=2,y=1,z=1 -> 4
    assert rc.jaccard_multiset(a, b) == pytest.approx(0.5)
    assert rc.jaccard_multiset(a, a) == pytest.approx(1.0)


# ------------------------------------------------------------------ robustness

def test_corrupt_cache_is_a_miss_not_a_crash(tmp_path):
    p = tmp_path / "decision-cache.json"
    p.write_text("not json{", encoding="utf-8")
    c = rc.TieredDecisionCache(str(p))
    assert _lookup(c, _lines())["tier"] is None


def test_eviction_at_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "CACHE_MAX_ENTRIES", 2)
    c = _cache(tmp_path)
    first = _lines(texts=("x = 1",))
    _store(c, first)
    _store(c, _lines(texts=("y = 1",)))
    _store(c, _lines(texts=("z = 1",)))
    assert _lookup(c, first)["tier"] is None


# ------------------------------------------------------------------ triggers

def _signals(**kw):
    base = {"langs": [], "n_lines": 0, "n_code_lines": 0,
            "has_test_file": False, "has_prose": False, "high_by_persona": {}}
    base.update(kw)
    return base


def test_trigger_docs_only_change(tmp_path):
    lines = _diff({"notes.md": "# hello\n"})
    langs_of = {ln["file"]: panel.lang_of(ln["file"]) for ln in lines}
    sig = rc.review_signals(lines, [], langs_of)
    trig = rc.evaluate_triggers(sig)
    assert trig["slop"]["triggered"] is True
    assert trig["perf"]["triggered"] is False
    assert trig["security"]["triggered"] is False
    assert trig["a11y"]["triggered"] is False


def test_trigger_large_py_diff_fires_perf_and_simplicity():
    sig = _signals(langs=["py"], n_lines=120, n_code_lines=110)
    trig = rc.evaluate_triggers(sig)
    assert trig["perf"]["triggered"] is True
    assert trig["perf"]["trigger"] == "diff-size>=20-code-lines"
    assert trig["simplicity"]["triggered"] is True
    assert trig["boundary"]["triggered"] is True  # py is an IO-edge lang


def test_trigger_small_py_diff_no_perf():
    sig = _signals(langs=["py"], n_lines=5, n_code_lines=5)
    trig = rc.evaluate_triggers(sig)
    assert trig["perf"]["triggered"] is False
    assert trig["simplicity"]["triggered"] is False
    assert trig["security"]["triggered"] is True  # file-type signal


def test_trigger_test_gap_signal():
    sig = _signals(langs=["py"], n_lines=10, n_code_lines=10,
                   has_test_file=False)
    assert rc.evaluate_triggers(sig)["tests"]["triggered"] is True
    assert rc.evaluate_triggers(sig)["tests"]["trigger"] == \
        "test-gap:code-without-test"
    sig2 = _signals(langs=["py"], n_lines=10, n_code_lines=10,
                    has_test_file=True)
    assert rc.evaluate_triggers(sig2)["tests"]["triggered"] is False


def test_trigger_risk_signal_without_file_type():
    # ADVERSARIAL for the trigger table: a HIGH security finding triggers
    # the security aspect even when the file-type signal alone would not.
    sig = _signals(langs=[], n_lines=3, n_code_lines=0,
                   high_by_persona={"security": True})
    trig = rc.evaluate_triggers(sig)
    assert trig["security"]["triggered"] is True
    assert trig["security"]["trigger"] == "risk:high-security-finding"
    assert trig["correctness"]["triggered"] is False


def test_trigger_a11y_ux_surface():
    sig = _signals(langs=["css"], n_lines=4, n_code_lines=4)
    trig = rc.evaluate_triggers(sig)
    assert trig["a11y"]["triggered"] is True
    assert trig["security"]["triggered"] is False


def test_external_should_run():
    assert rc.external_should_run(
        {a: {"triggered": False} for a in rc.ASPECTS}) is False
    trig = {a: {"triggered": False} for a in rc.ASPECTS}
    trig["perf"] = {"triggered": True, "trigger": "diff-size>=20-code-lines"}
    assert rc.external_should_run(trig) is True


# ------------------------------------------------------------------ cost table

def _trig(**over):
    base = {a: {"triggered": False, "trigger": None} for a in rc.ASPECTS}
    base.update(over)
    return base


def test_expected_calls_table_math():
    trig = _trig(perf={"triggered": True,
                       "trigger": "diff-size>=20-code-lines"})
    rows = rc.expected_calls_table(trig, external_possible=True,
                                   external_ran=True, local_ran=True,
                                   memoized_fraction=0.0)
    by = {r["leg"]: r for r in rows}
    assert set(by) == {"guardrails(local-panel)", "external(model-leg)"}
    # Guardrails row: always P=1, one call, measured actual.
    g = by["guardrails(local-panel)"]
    assert g["p_triggered"] == 1.0
    assert g["expected_calls"] == pytest.approx(1.0)
    assert g["actual_calls"] == 1
    # External leg: P=1 (possible and triggered), one model pass, measured.
    e = by["external(model-leg)"]
    assert e["p_triggered"] == 1.0
    assert e["expected_calls"] == pytest.approx(1.0)
    assert e["actual_calls"] == 1
    assert "diff-size>=20-code-lines" in (e["trigger"] or "")


def test_expected_calls_table_actuals_are_measured():
    # ADVERSARIAL (product B1): actual_calls must report what ran, never
    # what the triggers imply. Local-only run with fired triggers: the
    # external leg is not possible in this configuration, so p=0,
    # expected=0, actual=0 -- triggers alone never fabricate calls.
    trig = _trig(security={"triggered": True,
                           "trigger": "risk:high-security-finding"})
    rows = rc.expected_calls_table(trig, external_possible=False,
                                   external_ran=False, local_ran=True,
                                   memoized_fraction=0.0)
    by = {r["leg"]: r for r in rows}
    e = by["external(model-leg)"]
    assert e["p_triggered"] == 0.0  # not possible in this configuration
    assert e["expected_calls"] == pytest.approx(0.0)
    assert e["actual_calls"] == 0
    # Memoized run: the local leg did not run either.
    rows_m = rc.expected_calls_table(trig, external_possible=False,
                                     external_ran=False, local_ran=False,
                                     memoized_fraction=1.0)
    by_m = {r["leg"]: r for r in rows_m}
    assert by_m["guardrails(local-panel)"]["expected_calls"] == pytest.approx(0.0)
    assert by_m["guardrails(local-panel)"]["actual_calls"] == 0


def test_expected_calls_table_memoization_zeroes_guardrails():
    trig = _trig()
    rows = rc.expected_calls_table(trig, external_possible=True,
                                   external_ran=False, local_ran=False,
                                   memoized_fraction=1.0)
    by = {r["leg"]: r for r in rows}
    assert by["guardrails(local-panel)"]["expected_calls"] == pytest.approx(0.0)
    # The external leg is never memoized: untriggered here, P=0.
    assert by["external(model-leg)"]["p_triggered"] == 0.0
    assert by["external(model-leg)"]["trigger"] is None


def test_aspect_triggers_cover_all_registry_aspects():
    trig = rc.evaluate_triggers(_signals())
    for a in rc.ASPECTS:
        assert a in trig
        assert "triggered" in trig[a] and "trigger" in trig[a]


# ------------------------------------------------------------------ prior findings

def test_prior_findings_checksum(tmp_path):
    rd = tmp_path / "state" / "reviews"
    rd.mkdir(parents=True)
    art = {"base": "origin/main", "reviewed_at": "2026-10-09T01:00:00",
           "findings": [{"persona": "security", "check": "c",
                         "file": "a.py", "line": 1, "severity": "high"}]}
    (rd / "abc123.json").write_text(json.dumps(art), encoding="utf-8")
    (rd / "decision-cache.json").write_text(json.dumps({"version": 2}),
                                            encoding="utf-8")
    got = rc.prior_findings_checksum(str(tmp_path), "origin/main")
    assert got != rc.prior_findings_checksum(str(tmp_path), "other-base")
    # No artifact for this base -> the shared NO_PRIOR conditioning.
    assert rc.prior_findings_checksum(str(tmp_path), "other-base") == \
        rc.prior_findings_checksum(str(tmp_path), "nope")


def test_prior_findings_excludes_current_commit(tmp_path):
    # A re-run of the same commit sees the same prior conditioning as the
    # run that stored the entry; otherwise the exact tier could never hit
    # twice in a row (the run's own artifact would always invalidate it).
    rd = tmp_path / "state" / "reviews"
    rd.mkdir(parents=True)
    art = {"base": "origin/main", "reviewed_at": "2026-10-09T01:00:00",
           "findings": [{"persona": "security", "check": "c",
                         "file": "a.py", "line": 1, "severity": "high"}]}
    (rd / "abc123.json").write_text(json.dumps(art), encoding="utf-8")
    with_prior = rc.prior_findings_checksum(str(tmp_path), "origin/main")
    without = rc.prior_findings_checksum(str(tmp_path), "origin/main",
                                         exclude_sha="abc123")
    assert with_prior != without
    assert without == rc.prior_findings_checksum(str(tmp_path), "nope")


def test_review_signals_counts(tmp_path):
    lines = _diff({"svc/app.py": "x = 1\ny = 2\n",
                   "tests/test_app.py": "def test_x():\n    assert True\n"})
    langs_of = {ln["file"]: panel.lang_of(ln["file"]) for ln in lines}
    sig = rc.review_signals(lines, [], langs_of)
    assert sig["langs"] == ["py"]
    assert sig["n_lines"] == 4
    assert sig["n_code_lines"] == 4
    assert sig["has_test_file"] is True


def test_cache_key_excludes_machine_written_state():
    # The panel's own artifact must not enter the cache key: an untracked
    # artifact from run N lands in run N+1's diff, and if it keyed the
    # cache, the exact tier could never hit twice in a row.
    app = {"file": "svc/app.py", "line": 1, "text": "x = 1"}
    artifact = {"file": "state/reviews/deadbeef.json", "line": 1,
                "text": '{"verdict": "pass"}'}
    testline = {"file": "tests/test_app.py", "line": 1, "text": "x = 1"}
    key = [ln for ln in [app, artifact, testline]
           if not panel.EXEMPT.search(ln["file"])
           and not panel.SELF_REFERENTIAL.search(ln["file"])]
    assert key == [app]
    assert rc.canonical_key([app, artifact, testline]) != rc.canonical_key([app])


def test_cache_key_keeps_state_source():
    # The state/ exemption is by file kind, not directory: real source
    # under state/ is still reviewable and still keys the cache.
    src = {"file": "state/bus.py", "line": 1, "text": "x = 1"}
    key = [ln for ln in [src]
           if not panel.EXEMPT.search(ln["file"])
           and not panel.SELF_REFERENTIAL.search(ln["file"])]
    assert key == [src]


def test_key_lines_premise_exempt_lines_produce_no_findings():
    # Pins the safety premise of keying the cache on reviewable lines:
    # EXEMPT and SELF_REFERENTIAL lines contribute no findings, so
    # excluding them from the key cannot change the verdict being
    # replayed. Each planted line WOULD fire a HIGH check if reviewable.
    lines = _diff({
        "tests/test_x.py": "x = eval(user_input)\n",
        "state/reviews/old.json":
            '{"q": "SELECT * FROM t WHERE a = \'x\' + y"}\n',
        "svc/ok.py": "x = 1\n",
    })
    by_file = {ln["file"] for ln in lines}
    assert {"tests/test_x.py", "state/reviews/old.json", "svc/ok.py"} <= by_file
    key = [ln for ln in lines
           if not panel.EXEMPT.search(ln["file"])
           and not panel.SELF_REFERENTIAL.search(ln["file"])]
    assert [ln["file"] for ln in key] == ["svc/ok.py"]
    findings = panel.run_local(lines)
    cited = {f["file"] for f in findings}
    assert "tests/test_x.py" not in cited
    assert "state/reviews/old.json" not in cited
    # Sanity: the planted lines really are finding-shaped; run_local on
    # the exempt files alone (filter bypassed) fires.
    direct = panel.run_local([
        {"file": "svc/e.py", "line": 1, "text": "x = eval(user_input)"},
        {"file": "svc/q.py", "line": 1,
         "text": "q = \"SELECT * FROM t WHERE a = 'x' + y\""},
    ])
    assert {f["check"] for f in direct} >= {"eval-added", "sql-concat"}
