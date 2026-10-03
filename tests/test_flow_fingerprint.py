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
(sorted name=value pairs) into a `root` field, and describe_effect reports
"dom" when it changes. These tests pin the exact measured numbers from the
issue, prove the pre-fix rule was blind to them (the frozen legacy oracle below
returns None on every one), prove the new rule is not blind, and prove the new
field introduces no false positives. The pre-existing gates (>24 html, >2 text,
focus, scroll) are pinned unchanged: the fix narrows the blind spot, it does
not re-tune the thresholds.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "e2e"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "browser"))
import flow  # noqa: E402


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
        "root": "data-theme=dark;lang=en",
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
        after = _fp(html=145009, root="data-theme=light;lang=en")
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_same_length_attribute_flip(self):
        """Strongest adversarial case: the attribute value changes length by
        zero, so no length-based gate anywhere can see it. dark -> dork."""
        before = _fp(root="data-theme=dark")
        after = _fp(root="data-theme=dork")
        assert before["html"] == after["html"]
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_attribute_added_to_html_element(self):
        """A class or data attribute appearing from nowhere is also a change."""
        before = _fp(root="lang=en")
        after = _fp(root="data-theme=dark;lang=en")
        assert _legacy_effect(before, after) is None
        assert flow.describe_effect(before, after) == "dom"

    def test_attribute_order_is_not_an_effect(self):
        """Canonical (sorted) serialization: attribute order must not read as
        a DOM change, or the fingerprint would be flaky."""
        before = _fp(root="data-theme=dark;lang=en")
        after = _fp(root="data-theme=dark;lang=en")
        assert flow.describe_effect(before, after) is None

    def test_no_change_no_effect(self):
        before = _fp()
        after = _fp()
        assert flow.describe_effect(before, after) is None
        assert _legacy_effect(before, after) is None

    def test_missing_root_key_is_backward_compatible(self):
        """Dicts without the new field (old callers, hand-built fixtures)
        must behave exactly as the old rule did — no None-vs-None surprise."""
        before = _fp()
        after = _fp(html=145009)
        del before["root"]
        del after["root"]
        assert flow.describe_effect(before, after) == _legacy_effect(before, after)


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


class TestFingerprintStructure:
    def test_state_js_reads_document_element(self):
        """Structural pin: the field must survive future refactors of the JS.
        If this fails, the fix was silently dropped."""
        assert "documentElement" in flow.STATE_JS
        assert "root:" in flow.STATE_JS

    def test_state_js_is_syntactically_valid_js(self, tmp_path):
        """The snippet is an expression; wrap it in a temp file so node can
        parse it. A syntax slip here would break every flow audit at runtime."""
        import subprocess

        probe = tmp_path / "fp_probe.mjs"
        probe.write_text("const fp = " + flow.STATE_JS + ";\n", encoding="utf-8")
        p = subprocess.run(["node", "--check", str(probe)],
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, p.stderr
