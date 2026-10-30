import asyncio
import importlib.util
import json

from mcp import Client

from task_mcp.build import build


def import_from(path):
    spec = importlib.util.spec_from_file_location("built_server", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def list_tools(server):
    async def go():
        async with Client(server) as c:
            return {t.name: t for t in (await c.list_tools()).tools}
    return asyncio.run(go())


def test_built_server_is_valid_python(tmp_path):
    compile(build("examples/greenhouse/plan.yaml", tmp_path).read_text(), "server.py", "exec")


def test_built_server_lists_plan_tools(tmp_path):
    tools = list_tools(import_from(build("examples/greenhouse/plan.yaml", tmp_path)).server)
    assert set(tools) == {"search_jobs", "get_job"}
    assert tools["get_job"].annotations.read_only_hint is True


def test_every_tool_has_fields_param_and_required_params(tmp_path):
    tools = list_tools(import_from(build("examples/greenhouse/plan.yaml", tmp_path)).server)
    for t in tools.values():
        assert "fields" in t.input_schema["properties"]
    assert set(tools["get_job"].input_schema["required"]) == {"board", "id"}
    assert "dropped field" in tools["get_job"].description


def test_build_copies_plan_and_sources(tmp_path):
    build("examples/greenhouse/plan.yaml", tmp_path)
    assert (tmp_path / "plan.yaml").exists() and (tmp_path / "sources.yaml").exists()


def test_built_server_calls_runtime(tmp_path, monkeypatch):
    mod = import_from(build("examples/github/plan.yaml", tmp_path))
    issues = json.load(open("samples/gh_issues.json"))
    monkeypatch.setattr(mod.BACKEND, "get", lambda url, params: (200, issues))
    monkeypatch.setattr(mod, "EXTRACTOR", None)  # no model in unit tests
    out = json.loads(mod.list_issues(owner="facebook", repo="react"))
    assert out["count"] == 5
