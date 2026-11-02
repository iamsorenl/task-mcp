import json
import shutil

import pytest
import yaml

from task_mcp import cli
from task_mcp.sources import record
from tests.helpers import gh_backend, gh_list, gh_sources

GOOD = json.dumps({"scope": "s", "red_flags": []})


@pytest.fixture
def api_dir(tmp_path):
    (tmp_path / "sources.yaml").write_text(yaml.safe_dump(gh_sources()))
    shutil.copy("examples/greenhouse/plan.yaml", tmp_path / "plan.yaml")
    jid = gh_list()["jobs"][0]["id"]
    (tmp_path / "tasks.yaml").write_text(yaml.safe_dump({
        "preferences": "No 996.",
        "tasks": [{"id": "a", "q": f"Is job {jid} on board acme a fit?", "expected": {"fit": "no", "red_flags": []},
                   "checked": True},
                  {"id": "b", "q": "unchecked", "expected": {"fit": "no", "red_flags": []}, "checked": False}]}))
    record(gh_sources(), gh_backend(), tmp_path / "recordings")
    return tmp_path


def fake_chat_factory(model):
    def chat(messages, tools):
        return {"content": '{"fit": "no", "red_flags": []}', "tool_calls": [], "usage": {"in": 5, "out": 1}}
    return chat


def test_review_ok(api_dir, capsys):
    assert cli.main(["review", str(api_dir)]) == 0
    assert "search_jobs" in capsys.readouterr().out


def test_review_broken_plan_exits_1(api_dir):
    p = yaml.safe_load((api_dir / "plan.yaml").read_text())
    p["tools"][0]["endpoint"] = "nowhere"
    (api_dir / "plan.yaml").write_text(yaml.safe_dump(p))
    assert cli.main(["review", str(api_dir)]) == 1


def test_eval_writes_rows_per_arm_checked_only(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    assert cli.main(["eval", str(api_dir), "--only-checked"]) == 0
    rows = [json.loads(l) for l in (api_dir / "runs" / "results.jsonl").read_text().splitlines()]
    assert sorted(r["arm"] for r in rows) == ["lean", "raw", "shaped"] and all(r["task"] == "a" for r in rows)
    assert cli.main(["eval", str(api_dir), "--only-checked"]) == 0  # rerun replaces, not appends
    assert len((api_dir / "runs" / "results.jsonl").read_text().splitlines()) == 3


def test_report_writes_markdown(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    cli.main(["eval", str(api_dir), "--only-checked"])
    assert cli.main(["report", str(api_dir)]) == 0
    assert "## By arm" in (api_dir / "REPORT.md").read_text()


def test_propose_writes_proposed_and_keeps_plan(api_dir, monkeypatch):
    before = (api_dir / "plan.yaml").read_text()
    good = open("examples/greenhouse/plan.yaml").read()
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: good))
    assert cli.main(["propose", str(api_dir), "--task", "screen"]) == 0
    assert (api_dir / "plan.proposed.yaml").exists() and (api_dir / "plan.yaml").read_text() == before


def test_precompute_writes_stats(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    assert cli.main(["precompute", str(api_dir)]) == 0
    assert json.loads((api_dir / "runs" / "precompute.json").read_text())["items"] == 2


def test_build(api_dir, tmp_path):
    assert cli.main(["build", str(api_dir), "--out", str(tmp_path / "srv")]) == 0
    assert (tmp_path / "srv" / "server.py").exists()


def test_review_before_record_checks_shape_only(api_dir, capsys):
    shutil.rmtree(api_dir / "recordings")
    assert cli.main(["review", str(api_dir)]) == 0
    assert "task-mcp record" in capsys.readouterr().out


def test_eval_and_precompute_refuse_invalid_plan(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    p = yaml.safe_load((api_dir / "plan.yaml").read_text())
    p["tools"][0]["endpoint"] = "nowhere"
    (api_dir / "plan.yaml").write_text(yaml.safe_dump(p))
    assert cli.main(["eval", str(api_dir)]) == 1 and cli.main(["precompute", str(api_dir)]) == 1
    assert not (api_dir / "runs").exists()


def test_report_mixed_models_needs_model_flag(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    cli.main(["eval", str(api_dir), "--only-checked", "--model", "m1"])
    cli.main(["eval", str(api_dir), "--only-checked", "--model", "m2"])
    assert cli.main(["report", str(api_dir)]) == 1
    assert cli.main(["report", str(api_dir), "--model", "m2"]) == 0
    assert "`m2`" in (api_dir / "REPORT.md").read_text()


def test_eval_task_subset_keeps_other_rows(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    monkeypatch.setattr(cli, "COMPLETE_FACTORY", lambda provider, model, json_mode=False: (lambda p: GOOD))
    assert cli.main(["eval", str(api_dir)]) == 0  # tasks a and b, three arms
    assert cli.main(["eval", str(api_dir), "--tasks", "a", "--arms", "lean"]) == 0
    rows = [json.loads(l) for l in (api_dir / "runs" / "results.jsonl").read_text().splitlines()]
    assert sorted((r["arm"], r["task"]) for r in rows) == sorted((a, t) for a in ("raw", "shaped", "lean") for t in "ab")


def test_eval_unknown_task_id_exits_1(api_dir, monkeypatch):
    monkeypatch.setattr(cli, "CHAT_FACTORY", fake_chat_factory)
    assert cli.main(["eval", str(api_dir), "--tasks", "zzz"]) == 1
    assert not (api_dir / "runs" / "results.jsonl").exists()
