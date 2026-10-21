"""Oracle for tools/runtime/worker_wrap.py: a worker run inherits the lifecycle.

Drives the wrapper end to end as a subprocess, the way a cron worker would:
begin, gate decisions, evidence validation, and the stop gate, all against a
throwaway git repo in a temp dir. The one thing not covered here is `panel`,
which needs the real persona machinery and is covered by panel.py's own
selftest plus the dry-run in the PR description.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAP = [os.environ.get("PYTHON", "python3"), str(ROOT / "tools" / "runtime" / "worker_wrap.py")]


def run(*args: str, cwd: str | None = None, state_dir: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if state_dir:
        env["WORKER_WRAP_STATE"] = state_dir
    return subprocess.run([*WRAP, *args], capture_output=True, text=True,
                          timeout=60, cwd=cwd, env=env)


def git(*args: str, cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=30)


def make_repo() -> str:
    tmp = tempfile.mkdtemp(prefix="worker-wrap-test-")
    git("init", "-q", cwd=tmp)
    git("config", "user.email", "test@example.com", cwd=tmp)
    git("config", "user.name", "test", cwd=tmp)
    Path(tmp, "README.md").write_text("test repo\n")
    git("add", "-A", cwd=tmp)
    git("commit", "-qm", "init", cwd=tmp)
    return tmp


def prompt_file(text: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


def test_full_lifecycle_passes() -> None:
    repo = make_repo()
    state = tempfile.mkdtemp(prefix="worker-wrap-state-")
    prompt = prompt_file("Check the docs index\n- do not push to main\n- open an issue per broken link")
    try:
        proc = run("begin", "--worker", "t1", "--prompt-file", prompt, "--repo", repo,
                   state_dir=state)
        assert proc.returncode == 0, proc.stderr
        assert "session" in proc.stdout

        proc = run("gate", "--worker", "t1", "--action", "git status", state_dir=state)
        assert proc.returncode == 0

        proc = run("gate", "--worker", "t1", "--action", "git push origin feat/x", state_dir=state)
        assert proc.returncode == 3  # needs auth

        proc = run("gate", "--worker", "t1", "--action", "git push origin feat/x", "--authorized",
                   state_dir=state)
        assert proc.returncode == 0

        proc = run("gate", "--worker", "t1", "--action", "git reset --hard", state_dir=state)
        assert proc.returncode == 2  # deny

        claims = [{"claim": "repo initialized", "evidence": ["file:README.md"]}]
        claims_path = os.path.join(repo, "claims.json")
        Path(claims_path).write_text(json.dumps(claims))
        proc = run("check-evidence", "--worker", "t1", "--claims", claims_path, "--repo", repo,
                   state_dir=state)
        assert proc.returncode == 0, proc.stdout

        proc = run("end", "--worker", "t1", "--repo", repo,
                   "--claims", claims_path, "--summary", "dry run ok", state_dir=state)
        assert proc.returncode == 1, proc.stdout  # FAIL: a DENY row exists in the gate log
        assert "no_denied_actions" in proc.stdout
    finally:
        os.unlink(prompt)


def test_clean_run_passes_stop_gate() -> None:
    repo = make_repo()
    state = tempfile.mkdtemp(prefix="worker-wrap-state-")
    prompt = prompt_file("List open issues\n- read only, no external effects")
    try:
        assert run("begin", "--worker", "t2", "--prompt-file", prompt, "--repo", repo,
                   state_dir=state).returncode == 0
        assert run("gate", "--worker", "t2", "--action", "gh issue list",
                   state_dir=state).returncode == 0
        proc = run("end", "--worker", "t2", "--repo", repo, "--summary", "read-only run",
                   state_dir=state)
        assert proc.returncode == 0, proc.stdout
        assert "PASS" in proc.stdout
    finally:
        os.unlink(prompt)


def test_evidence_failure_blocks() -> None:
    repo = make_repo()
    state = tempfile.mkdtemp(prefix="worker-wrap-state-")
    prompt = prompt_file("Do things\n- claim them")
    try:
        assert run("begin", "--worker", "t3", "--prompt-file", prompt, "--repo", repo,
                   state_dir=state).returncode == 0
        claims_path = os.path.join(repo, "claims.json")
        Path(claims_path).write_text(json.dumps(
            [{"claim": "did the thing", "evidence": ["file:missing.txt"]},
             {"claim": "no evidence at all", "evidence": []}]))
        proc = run("check-evidence", "--worker", "t3", "--claims", claims_path, "--repo", repo,
                   state_dir=state)
        assert proc.returncode == 1
        assert "2/2 claims unresolved" in proc.stdout
    finally:
        os.unlink(prompt)


def test_selftest_subcommand() -> None:
    proc = run("selftest")
    assert proc.returncode == 0, proc.stdout
    assert "0 failure(s)" in proc.stdout
