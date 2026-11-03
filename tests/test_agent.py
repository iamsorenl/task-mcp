import pytest

from task_mcp.agent import run_task, tool_schemas
from task_mcp.arms import arm_plan
from task_mcp.plan import load_plan
from task_mcp.runtime import call_tool
from task_mcp.sources import ReplayBackend, record
from tests.helpers import gh_backend, gh_list, gh_sources

SRC = gh_sources()
PLAN = load_plan("examples/greenhouse/plan.yaml")
TASK = {"id": "t1", "q": "Is job 1 a fit?"}


@pytest.fixture
def rb(tmp_path):
    record(SRC, gh_backend(), tmp_path)
    return ReplayBackend(tmp_path)


def tool(plan, name):
    return next(t for t in plan["tools"] if t["name"] == name)


def fake_chat(replies, usage=(100, 10)):
    replies, seen = list(replies), []

    def chat(messages, tools):
        seen.append(messages)
        r = replies.pop(0)
        return {**r, "usage": {"in": usage[0], "out": usage[1]}}
    chat.seen = seen
    return chat


def call(name, args):
    return {"content": "", "tool_calls": [{"name": name, "args": args}]}


def final(text):
    return {"content": text, "tool_calls": []}


def test_raw_arm_has_one_tool_per_endpoint():
    raw = arm_plan(PLAN, SRC, "raw")
    assert [t["name"] for t in raw["tools"]] == ["list_jobs", "get_job"]
    assert set(tool(raw, "get_job")["params"]) == {"board", "id"}


def test_raw_arm_returns_raw_body(rb):
    r = call_tool(arm_plan(PLAN, SRC, "raw"), SRC, "get_job", {"board": "acme", "id": gh_list()["jobs"][0]["id"]}, rb)
    assert r == gh_list()["jobs"][0]


def test_shaped_arm_keeps_all_fields_but_filters(rb):
    shaped = arm_plan(PLAN, SRC, "shaped")
    assert "extracts" not in shaped or not shaped["extracts"]
    r = call_tool(shaped, SRC, "search_jobs", {"board": "acme", "location": "singapore"}, rb)
    assert r["count"] == 1 and "content" in r["items"][0]


def test_lean_arm_is_the_plan():
    assert arm_plan(PLAN, SRC, "lean")["tools"] == PLAN["tools"]


def test_tool_schemas_ollama_format():
    s = {x["function"]["name"]: x["function"] for x in tool_schemas(PLAN)}
    assert s["get_job"]["parameters"]["required"] == ["board", "id"]
    assert s["get_job"]["parameters"]["properties"]["fields"]["type"] == "array"
    assert "fields" not in {x["function"]["name"]: x["function"] for x in tool_schemas(arm_plan(PLAN, SRC, "raw"))}["get_job"]["parameters"]["properties"]


def test_usage_summed_across_turns():
    out = run_task(fake_chat([call("get_job", {"board": "a", "id": "1"}), final('{"fit": "no"}')]),
                   PLAN, TASK, respond=lambda n, a: "{}")
    assert out["tokens_in"] == 200 and out["tokens_out"] == 20 and out["final"] == '{"fit": "no"}'


def test_preferences_in_system_prompt():
    chat = fake_chat([final("x")])
    run_task(chat, PLAN, TASK, respond=lambda n, a: "{}", preferences="No 996.")
    assert "No 996." in chat.seen[0][0]["content"]


def test_oversized_result_truncated_and_counted():  # Review Focus 5
    out = run_task(fake_chat([call("get_job", {"id": "1"}), final("x")]), PLAN, TASK,
                   respond=lambda n, a: "x" * 100_000, max_tool_chars=60_000)
    assert out["truncations"] == 1 and out["calls"][0]["chars"] == 60_000


def test_fallback_calls_counted():
    out = run_task(fake_chat([call("get_job", {"id": "1", "fields": ["updated_at"]}), final("x")]), PLAN, TASK,
                   respond=lambda n, a: "{}")
    assert out["fallback_calls"] == 1


def test_repeat_call_blocked():
    seen = []
    out = run_task(fake_chat([call("get_job", {"id": "1"}), call("get_job", {"id": "1"}), final("x")]), PLAN, TASK,
                   respond=lambda n, a: seen.append(n) or "{}")
    assert len(seen) == 1 and out["repeats"] == 1


def test_step_limit():
    out = run_task(fake_chat([call("get_job", {"id": str(i)}) for i in range(3)]), PLAN, TASK,
                   respond=lambda n, a: "{}", max_steps=3)
    assert out["stopped"] == "step_limit"


def test_tool_exception_goes_back_to_agent():  # the live MCP server returns errors to the agent too
    def boom(n, a):
        raise KeyError("board")
    chat = fake_chat([call("get_job", {"id": "1"}), final("done")])
    out = run_task(chat, PLAN, TASK, respond=boom)
    assert out["stopped"] is None and out["final"] == "done"
    assert "KeyError" in next(m for m in chat.seen[1] if m["role"] == "tool")["content"]
