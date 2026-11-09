#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""a2a bridge to Gemini (free AI Studio tier) — the decorrelated second reviewer that
replaces Codex (ADR-0007 amended). Different model family = real independence for the
agreement gate (ADR-0004/0008). Model is an interchangeable ACTOR, not a fixed persona.

Auth: GEMINI_API_KEY env (free at aistudio.google.com/apikey).
Usage: a2a-gemini-call.py "<prompt>" [--model gemini-2.5-flash]
Returns JSON: {state, model, response_text, duration_ms, error?}

Audit: every call is logged to ~/.claude/cache/a2a/audit.jsonl via a2a-audit.py
(night-rick#13). Before this change the amended ADR-0007 reviewer left zero
trace in the canonical record, so the agreement oracle could never pass for a
Gemini second review. Logging never changes the returned JSON or the exit
code: a logging failure is swallowed, the call result is what it is.
"""
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _import_audit():
    """Load a2a-audit.py from the deployed bin dir, or None when absent."""
    try:
        audit_path = Path.home() / ".claude" / "bin" / "a2a-audit.py"
        spec = importlib.util.spec_from_file_location("a2a_audit", audit_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _log_call(result, prompt):
    """Append one audit record. Never raises; never changes the result."""
    try:
        audit = _import_audit()
        if audit is None:
            return
        extra = {}
        if result.get("state") != "completed" and result.get("error"):
            extra["error"] = str(result["error"])[:200]
        audit.log_call(
            "claude:home",
            f"gemini:{result.get('model', MODEL)}",
            audit.hash_prompt(prompt),
            int(result.get("duration_ms", 0)),
            str(result.get("state", "failed")),
            None,
            **extra,
        )
    except Exception:
        return

MODEL = "gemini-2.5-flash"
if "--model" in sys.argv:
    MODEL = sys.argv[sys.argv.index("--model") + 1]
prompt = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else sys.stdin.read()


def call(prompt, model):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {"state": "auth_failed", "model": model, "error": "GEMINI_API_KEY not set"}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.2}}).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=90).read())
        text = r["candidates"][0]["content"]["parts"][0]["text"]
        return {"state": "completed", "model": model, "response_text": text,
                "duration_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"state": "failed", "model": model, "error": f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"}
    except Exception as e:
        return {"state": "failed", "model": model, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    result = call(prompt, MODEL)
    _log_call(result, prompt)
    print(json.dumps(result, ensure_ascii=False))
