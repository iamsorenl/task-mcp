import json
import subprocess
from types import SimpleNamespace

import pytest
import yaml

from task_mcp.plan import validate
from task_mcp.propose import ProposeError, build_prompt, propose
from task_mcp.providers import claude_code_complete, ollama_chat
from task_mcp.sources import record
from tests.helpers import BASE, FakeBackend, gh_backend, gh_list, gh_sources

SRC = gh_sources()
GOOD_YAML = open("examples/greenhouse/plan.yaml").read()
BAD_YAML = GOOD_YAML.replace("endpoint: get_job", "endpoint: unknown_endpoint")


def fake(calls, *replies):
    def complete(prompt):
        calls.append(prompt)
        return replies[min(len(calls), len(replies)) - 1]
    return complete


@pytest.fixture
def rec_dir(tmp_path):
    record(SRC, gh_backend(), tmp_path)
    return tmp_path


@pytest.fixture
def big_rec_dir(tmp_path):  # Review Focus 5: a board with 673 long jobs
    job = gh_list()["jobs"][0]
    jobs = [{**job, "id": i, "content": job["content"] * 4} for i in range(673)]
    record(gh_sources(max_details=3), FakeBackend({f"{BASE}/boards/acme/jobs": {"jobs": jobs},
                                                   **{f"{BASE}/boards/acme/jobs/{i}": jobs[i] for i in range(3)}}), tmp_path)
    return tmp_path


def test_prompt_capped_and_samples_three(big_rec_dir):
    p = build_prompt(SRC, big_rec_dir, "screen jobs")
    assert len(p) <= 20_000 and p.count('"absolute_url"') <= 3


def test_prompt_has_inventory_and_task(rec_dir):
    p = build_prompt(SRC, rec_dir, "screen jobs")
    assert "screen jobs" in p and "location.name" in p and "bookshop" in p


def test_propose_returns_valid_plan(rec_dir):
    plan = propose(SRC, rec_dir, "t", fake([], "```yaml\n" + GOOD_YAML + "\n```"))
    assert validate(plan, SRC, rec_dir) == []


def test_propose_retries_with_errors_then_succeeds(rec_dir):
    calls = []
    propose(SRC, rec_dir, "t", fake(calls, BAD_YAML, GOOD_YAML))
    assert len(calls) == 2 and "unknown_endpoint" in calls[1]


def test_propose_retries_on_unparseable_yaml(rec_dir):  # Review Focus 3
    calls = []
    propose(SRC, rec_dir, "t", fake(calls, "tools: [unclosed", GOOD_YAML))
    assert len(calls) == 2


def test_propose_raises_after_two_bad(rec_dir):
    with pytest.raises(ProposeError):
        propose(SRC, rec_dir, "t", fake([], BAD_YAML, BAD_YAML))


def test_claude_code_complete_parses_result(monkeypatch):
    seen = {}

    def run(cmd, input, capture_output, text, cwd=None):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "x"}), stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    assert claude_code_complete()("hi") == "x" and seen["cmd"][:2] == ["claude", "-p"]


def test_claude_code_complete_raises_on_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="not logged in"))
    with pytest.raises(RuntimeError, match="not logged in"):
        claude_code_complete()("hi")


def test_ollama_chat_returns_usage():
    msg = SimpleNamespace(content="", tool_calls=[SimpleNamespace(function=SimpleNamespace(name="t", arguments={"a": 1}))])
    client = SimpleNamespace(chat=lambda **kw: SimpleNamespace(message=msg, prompt_eval_count=100, eval_count=7))
    out = ollama_chat("m", client=client)([{"role": "user", "content": "q"}], [])
    assert out == {"content": "", "tool_calls": [{"name": "t", "args": {"a": 1}}], "usage": {"in": 100, "out": 7}}


@pytest.mark.ollama
def test_live_propose_greenhouse_valid(rec_dir):
    from task_mcp.providers import ollama_complete
    plan = propose(SRC, rec_dir, "Screen job postings for fit against my preferences.", ollama_complete("gpt-oss:20b"))
    assert validate(plan, SRC, rec_dir) == []


def test_claude_code_runs_without_tools_or_mcp_in_empty_dir(monkeypatch):  # samples are untrusted API text
    seen = {}

    def run(cmd, input, capture_output, text, cwd):
        seen.update(cmd=cmd, cwd=cwd)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "x"}), stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    claude_code_complete()("hi")
    i = seen["cmd"].index("--tools")
    assert seen["cmd"][i + 1] == "" and "--strict-mcp-config" in seen["cmd"]
    from pathlib import Path
    assert seen["cwd"] != str(Path.cwd()) and not list(Path(seen["cwd"]).iterdir()) if Path(seen["cwd"]).exists() else True


def test_ollama_complete_can_turn_thinking_off_and_cap_output():
    from task_mcp.providers import ollama_complete
    seen = {}

    def chat(**kw):
        seen.update(kw)
        return SimpleNamespace(message=SimpleNamespace(content="{}"))
    ollama_complete("m", json_mode=True, think=False, max_out=1500, client=SimpleNamespace(chat=chat))("p")
    assert seen["think"] is False and seen["format"] == "json" and seen["options"]["num_predict"] == 1500


def test_cli_extractor_turns_thinking_off(monkeypatch):
    from task_mcp import cli
    seen = {}
    monkeypatch.setattr(cli, "ollama_complete", lambda model, **kw: seen.update(kw) or (lambda p: "{}"))
    cli.COMPLETE_FACTORY("ollama", "gemma4:12b", json_mode=True)
    assert seen.get("think") is False and seen.get("max_out")


def test_claude_code_is_error_with_exit_0_raises(monkeypatch):
    out = json.dumps({"is_error": True, "result": "usage limit reached"})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=out, stderr=""))
    with pytest.raises(RuntimeError, match="usage limit"):
        claude_code_complete()("hi")


def test_claude_code_skips_user_settings(monkeypatch):  # no user hooks or plugins run on untrusted text
    seen = {}
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: seen.update(cmd=cmd) or
                        SimpleNamespace(returncode=0, stdout=json.dumps({"result": "x"}), stderr=""))
    claude_code_complete()("hi")
    i = seen["cmd"].index("--setting-sources")
    assert seen["cmd"][i + 1] == ""


def test_retry_errors_survive_prompt_cap(rec_dir, monkeypatch):
    import task_mcp.propose as pm
    monkeypatch.setattr(pm, "MAX_PROMPT", 2000)  # the inventory alone overflows it
    p = build_prompt(SRC, rec_dir, "t", errors=["MARKER problem"])
    assert len(p) <= 2000 and "MARKER problem" in p
