"""The flow audit's state fingerprint must see attribute-only DOM changes.

Measured 2026-08-08 (claude-setup#57) against daily-deep-learning: `#themeToggle`
flips `document.documentElement.dataset.theme` (dark -> light), repainting the
whole page. The fingerprint recorded only url / node count / body.innerText /
body.innerHTML lengths / activeElement / scrollY. Measured before/after:

    documentElement.dataset.theme:  dark -> light
    computed body background-color:  rgb(11, 9, 17) -> rgb(233, 224, 204)
    body.innerHTML.length:           144999 -> 145009   (+10, under the >24 gate)
    querySelectorAll("*").length:    180 -> 180         (zero node movement)

A full repaint no human could miss was invisible to the oracle, so the control
was reported dead. 11 of 17 flow failures in that e2e report were false, and a
required domain whose failures are majority-false trains the reader to skim it.

The fix: STATE_JS serializes document.documentElement's attributes canonically
(sorted [name, value] pairs as JSON) into a `root` field, and describe_effect
reports "dom" when it changes. Scope is the <html>-attribute class: the theme
toggle is the measured instance (7 of the 11 false failures); `#sndToggle` is
stated in the issue to be the same class, but its mechanism was not re-measured
in this repo, so no claim is made about it here. These tests pin the exact
measured numbers from the issue, prove the pre-fix rule was blind to them (the
frozen legacy oracle below returns None on every one), prove the new rule is
not blind, and prove the new field introduces no false positives for the
enumerated cases (identical fingerprints, attribute reordering, both dicts
missing `root`). The pre-existing gates (>24 html, >2 text, focus, scroll)
are pinned unchanged: the fix narrows the blind spot, it does not re-tune
the thresholds.

The live half of the regression protection is `flow.py selftest`, which plants
a theme toggle whose only effect is an <html> attribute flip and asserts the
flow report marks it live; the tests below pin the logic and execute STATE_JS
against a stub DOM, so a refactor that guts the JS while keeping its tokens
fails here too.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "e2e"))
import flow  # noqa: E402


def _root(*pairs):
    """The exact string STATE_JS produces for <html> attributes: JSON of the
    pairs sorted by name then value, or "" when there are none. Written with
    the same separators as JSON.stringify so hand-built fixtures match live
    fingerprints byte for byte."""
    if not pairs:
        return ""
    return json.dumps([[n, v] for n, v in sorted(pairs)],
                      separators=(",", ":"))


def _legacy_effect(before, after):
    """The describe_effect rule as it stood before the #57 fix, frozen.

    It is kept here verbatim (minus the new root check) as a regression oracle:
    any case in the blind-spot classes must return None under this function and
    "dom" under the real one. If a test below ever passes against _legacy_effect
    too, it is not testing the fix.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    if before.get("url") != after.get("url"):
        return "navigated"
    if abs((after.get("nodes") or 0) - (before.get("nodes") or 0)) >= 1:
        return "dom"
    if abs((after.get("html") or 0) - (before.get("html") or 0)) > 24:
        return "dom"
    if abs((after.get("text") or 0) - (before.get("text") or 0)) > 2:
        return "text"
    if before.get("focus") != after.get("focus"):
        return "focus"
    if abs((after.get("scroll") or 0) - (before.get("scroll") or 0)) > 8:
        return "scroll"
    return None


def _fp(**over):
    """A fingerprint dict shaped like STATE_JS output; `root` defaults to a
    themed <html> so tests must opt out of it explicitly."""
    d = {
        "url": "http://127.0.0.1:9999/route",
        "nodes": 180,
        "text": 5000,
        "html": 144999,
        "root": _root(("data-theme", "dark"), ("lang", "en")),
        "focus": "BUTTON#themeToggle",
        "scroll": 0,
    }
    d.update(over)
    return d


class TestIssue57BlindSpot:
    def test_measured_theme_toggle_case(self):
        """The exact numbers from the issue: +10 html delta, 180 nodes both
        sides, dataset.theme dark -> light. The old rule saw nothing."""
        before = _fp()
        after = _fp(html=145009,
                    root=_root(("data-theme", "light"), ("lang", "en")))
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_same_length_attribute_flip(self):
        """Strongest adversarial case: the attribute value changes length by
        zero, so no length-based gate anywhere can see it. dark -> dork."""
        before = _fp(root=_root(("data-theme", "dark")))
        after = _fp(root=_root(("data-theme", "dork")))
        assert before["html"] == after["html"]
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_attribute_added_to_html_element(self):
        """A class or data attribute appearing from nowhere is also a change."""
        before = _fp(root=_root(("lang", "en")))
        after = _fp(root=_root(("data-theme", "dark"), ("lang", "en")))
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_attribute_order_is_not_an_effect(self):
        """Canonical (sorted) serialization: attribute order must not read as
        a DOM change, or the fingerprint would be flaky."""
        before = _fp(root=_root(("data-theme", "dark"), ("lang", "en")))
        after = _fp(root=_root(("data-theme", "dark"), ("lang", "en")))
        assert flow.describe_effect(before, after) is None

    def test_no_change_no_effect(self):
        before = _fp()
        after = _fp()
        assert flow.describe_effect(before, after) is None
        assert _legacy_effect(before, after) is None

    def test_missing_root_key_is_backward_compatible(self):
        """Dicts without the new field (old callers, hand-built fixtures)
        must behave exactly as the old rule did, no None-vs-None surprise."""
        before = _fp()
        after = _fp(html=145009)
        del before["root"]
        del after["root"]
        assert flow.describe_effect(before, after) == _legacy_effect(before, after)

    def test_missing_root_vs_empty_root_is_no_change(self):
        """An old fingerprint (no root key) compared against a new one for a
        bare <html> (root="") must not read as a DOM change."""
        before = _fp()
        after = _fp(root="")
        del before["root"]
        assert flow.describe_effect(before, after) is None
        assert flow.describe_effect(after, before) is None

    def test_non_string_root_is_coerced(self):
        """A non-string root value must not read as a change against its
        own string form, including falsy values (0, False, []) that
        `x or ""` would collapse to "" before str() runs."""
        assert flow.describe_effect(_fp(root=1), _fp(root="1")) is None
        assert flow.describe_effect(_fp(root=0), _fp(root="0")) is None
        assert flow.describe_effect(_fp(root=False), _fp(root="False")) is None
        assert flow.describe_effect(_fp(root=[]), _fp(root="[]")) is None

    def test_root_change_beats_text_change(self):
        """Precedence is a decision, not an accident: a control that flips
        both a root attribute and visible text reports "dom", the same way
        the node and html gates already mask the text gate."""
        before = _fp()
        after = _fp(text=5003,
                    root=_root(("data-theme", "light"), ("lang", "en")))
        assert flow.describe_effect(before, after) == "dom"


class TestExistingGatesUnchanged:
    """The fix adds a blind-spot check; it must not re-tune the old gates."""

    def test_html_gate_still_24(self):
        assert flow.describe_effect(_fp(), _fp(html=144999 + 25)) == "dom"
        assert flow.describe_effect(_fp(), _fp(html=144999 + 24)) is None

    def test_text_gate_still_2(self):
        assert flow.describe_effect(_fp(), _fp(text=5003)) == "text"
        assert flow.describe_effect(_fp(), _fp(text=5002)) is None

    def test_node_gate_still_1(self):
        assert flow.describe_effect(_fp(), _fp(nodes=181)) == "dom"

    def test_focus_scroll_navigated_unchanged(self):
        assert flow.describe_effect(_fp(), _fp(focus="INPUT#n")) == "focus"
        assert flow.describe_effect(_fp(), _fp(scroll=9)) == "scroll"
        assert flow.describe_effect(_fp(), _fp(url="http://127.0.0.1:9999/other")) == "navigated"

    def test_non_dict_inputs(self):
        assert flow.describe_effect(None, {}) is None
        assert flow.describe_effect("x", "y") is None


def _run_state_js(attrs, tmp_path):
    """Execute STATE_JS in node against a stub DOM whose <html> carries
    `attrs` (a list of [name, value] pairs, in the given order) and return
    the fingerprint dict. This is the producer-side proof the hand-built
    dict tests cannot give: it runs the real JS, not a substring of it.

    The stub's `documentElement.attributes` is shaped like a real
    NamedNodeMap (numeric indices + length, no array methods), not a plain
    JS array, so a future refactor that used an array-only API would fail
    here instead of passing in test and breaking in a real page."""
    attrs_obj = {str(i): {"name": n, "value": v}
                 for i, (n, v) in enumerate(attrs)}
    attrs_obj["length"] = len(attrs)
    probe = tmp_path / "fp_exec.mjs"
    probe.write_text(
        "const document = {\n"
        "  querySelectorAll: () => new Array(180),\n"
        "  body: { innerText: 'x'.repeat(5000), innerHTML: 'y'.repeat(144999) },\n"
        "  documentElement: { attributes: "
        + json.dumps(attrs_obj) + " },\n"
        "  activeElement: null,\n"
        "};\n"
        "const location = { href: 'http://127.0.0.1:9999/route' };\n"
        "const window = { scrollY: 0 };\n"
        "const fp = " + flow.STATE_JS + ";\n"
        "console.log(JSON.stringify(fp));\n",
        encoding="utf-8")
    p = subprocess.run(["node", str(probe)], capture_output=True,
                       text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# The STATE_JS execution tests shell out to node, which no CI step
# installs; on a node-less runner they skip (reported in pytest's skipped
# count) instead of erroring the whole suite for an environment reason.
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is required to execute STATE_JS")


@requires_node
class TestStateJsExecution:
    def test_state_js_runs_and_reports_measured_fields(self, tmp_path):
        """The stub wiring is not vacuous: the executed snippet returns the
        issue's measured shape (180 nodes, 5000 text, 144999 html)."""
        fp = _run_state_js([["lang", "en"], ["data-theme", "dark"]], tmp_path)
        assert fp["url"] == "http://127.0.0.1:9999/route"
        assert fp["nodes"] == 180
        assert fp["text"] == 5000
        assert fp["html"] == 144999
        assert fp["focus"] == ""
        assert fp["scroll"] == 0

    def test_state_js_sorts_attributes_canonically(self, tmp_path):
        """Attributes handed to the snippet out of order come back sorted by
        name then value, so attribute order alone never reads as a change."""
        fp = _run_state_js([["lang", "en"], ["data-theme", "dark"]], tmp_path)
        assert fp["root"] == _root(("data-theme", "dark"), ("lang", "en"))

    def test_state_js_root_serialization_is_injective(self, tmp_path):
        """Two distinct attribute sets must never serialize identically.
        The old `name=value` joined by `;` encoding collided here: one
        attribute {a: "x;y=z"} and two attributes {a: "x", y: "z"} both
        produced "a=x;y=z". JSON pairs cannot collide."""
        one = _run_state_js([["a", "x;y=z"]], tmp_path)
        two = _run_state_js([["a", "x"], ["y", "z"]], tmp_path)
        assert one["root"] == '[["a","x;y=z"]]'
        assert two["root"] == '[["a","x"],["y","z"]]'
        assert one["root"] != two["root"]

    def test_state_js_same_length_flip_visible(self, tmp_path):
        """The issue's strongest case at the JS level: dark -> dork changes
        no length anywhere, but the executed root value still moves."""
        before = _run_state_js([["data-theme", "dark"]], tmp_path)
        after = _run_state_js([["data-theme", "dork"]], tmp_path)
        assert before["html"] == after["html"]
        assert before["root"] != after["root"]
        assert flow.describe_effect(before, after) == "dom"

    def test_state_js_empty_attributes_is_empty_string(self, tmp_path):
        """A bare <html> serializes to "", the value the missing-key
        normalization treats as equal."""
        fp = _run_state_js([], tmp_path)
        assert fp["root"] == ""


class TestFingerprintStructure:
    def test_state_js_reads_document_element(self):
        """Structural pin: the field must survive future refactors of the JS.
        If this fails, the fix was silently dropped."""
        assert "documentElement" in flow.STATE_JS
        assert "root:" in flow.STATE_JS

    @requires_node
    def test_state_js_is_syntactically_valid_js(self, tmp_path):
        """The snippet is an expression; wrap it in a temp file so node can
        parse it. A syntax slip here would break every flow audit at runtime."""
        probe = tmp_path / "fp_probe.mjs"
        probe.write_text("const fp = " + flow.STATE_JS + ";\n", encoding="utf-8")
        p = subprocess.run(["node", "--check", str(probe)],
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, p.stderr
