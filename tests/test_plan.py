import copy

import pytest

from task_mcp.plan import estimate, load_plan, summary, validate
from task_mcp.sources import record
from tests.helpers import gh_backend, gh_sources

SRC = gh_sources()
PLAN = load_plan("examples/greenhouse/plan.yaml")


@pytest.fixture
def rec_dir(tmp_path):
    record(SRC, gh_backend(), tmp_path)
    return tmp_path


def plan_with(**get_job_overrides):
    p = copy.deepcopy(PLAN)
    p["tools"][1].update(get_job_overrides)
    return p


def test_load_resolves_sources_path():
    assert PLAN["sources_path"].endswith("examples/greenhouse/sources.yaml")


def test_example_plan_is_valid():
    assert validate(PLAN, SRC) == []


def test_validate_catches_unknown_extract_and_bad_rule():
    errs = validate(plan_with(fields={"content": {"extract": "nope"}, "title": "maybe"}), SRC)
    assert any("nope" in e for e in errs) and any("maybe" in e for e in errs)


def test_validate_catches_unknown_endpoint_and_schema_type():
    p = plan_with(endpoint="nowhere")
    p["extracts"]["description_facts"]["schema"]["scope"]["type"] = "number"
    errs = validate(p, SRC)
    assert any("nowhere" in e for e in errs) and any("number" in e for e in errs)


def test_validate_catches_bad_filter_path(rec_dir):
    p = copy.deepcopy(PLAN)
    p["tools"][0]["params"]["query"]["filter"] = "nope.path"
    assert any("nope.path" in e for e in validate(p, SRC, rec_dir))


def test_estimate_after_smaller(rec_dir):
    e = estimate(PLAN, SRC, rec_dir)
    assert e["get_job"]["after"] < e["get_job"]["before"]
    assert e["search_jobs"]["after"] < e["search_jobs"]["before"]


def test_summary_lists_dropped_with_reason(rec_dir):
    s = summary(PLAN, SRC, rec_dir)
    assert "dropped" in s and "Legal boilerplate" in s and "extract" in s
