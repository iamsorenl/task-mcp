import json
from pathlib import Path

import pytest

from task_mcp.plan import load_plan
from task_mcp.runtime import call_tool
from task_mcp.sources import ReplayBackend, record
from tests.helpers import FakeBackend, gh_backend, gh_list, gh_sources

SRC = gh_sources()
PLAN = load_plan("examples/greenhouse/plan.yaml")
JOB_ID = str(gh_list()["jobs"][0]["id"])


@pytest.fixture
def rb(tmp_path):
    record(SRC, gh_backend(), tmp_path)
    return ReplayBackend(tmp_path)


def test_search_filters_and_shapes(rb):
    r = call_tool(PLAN, SRC, "search_jobs", {"board": "acme", "query": "account executive"}, rb)
    assert r["count"] == 2
    assert set(r["items"][0]) <= {"id", "title", "location", "departments", "absolute_url"}


def test_location_filter_is_case_insensitive(rb):
    r = call_tool(PLAN, SRC, "search_jobs", {"board": "acme", "location": "singapore"}, rb)
    assert [i["title"] for i in r["items"]] == ["Account Executive - DNB"]


def test_get_job_without_extractor_serves_text_not_html(rb):
    r = call_tool(PLAN, SRC, "get_job", {"board": "acme", "id": JOB_ID}, rb)
    assert "<p>" not in r["content"] and "&lt;" not in r["content"] and "data_compliance" not in r


def test_fallback_fields_returns_dropped_and_logs(rb, tmp_path):
    log = tmp_path / "fb.jsonl"
    r = call_tool(PLAN, SRC, "get_job", {"board": "acme", "id": JOB_ID, "fields": ["updated_at"]}, rb, log_path=log)
    assert "updated_at" in r["_fields"]
    row = json.loads(log.read_text())
    assert row["tool"] == "get_job" and row["path"] == "updated_at" and row["item_id"] == JOB_ID


def test_bad_board_returns_error_text(rb):  # Review Focus 1
    assert "error" in call_tool(PLAN, SRC, "search_jobs", {"board": "nope"}, rb)


def test_missing_required_param_is_error(rb):
    assert "board" in call_tool(PLAN, SRC, "search_jobs", {}, rb)["error"]


def test_unknown_tool_is_error(rb):
    assert "error" in call_tool(PLAN, SRC, "delete_everything", {}, rb)


def test_github_plan_runs_with_no_core_changes(tmp_path):  # generality check
    gsrc = load_plan("examples/github/plan.yaml")
    from task_mcp.sources import load_sources
    src = load_sources("examples/github/sources.yaml")
    issues = json.loads(Path("samples/gh_issues.json").read_text())
    record(src, FakeBackend({"https://api.github.com/repos/facebook/react/issues": issues}), tmp_path)
    r = call_tool(gsrc, src, "list_issues", {"owner": "facebook", "repo": "react"}, ReplayBackend(tmp_path))
    assert r["count"] == 5
    assert set(r["items"][0]) <= {"number", "title", "state", "labels", "user", "body"}
    assert "reactions" not in r["items"][0]


def test_core_has_no_api_names():
    src = "".join(p.read_text() for p in Path("src/task_mcp").glob("*.py")).lower()
    assert not any(w in src for w in ("greenhouse", "github", "job", "lever", "ashby"))
