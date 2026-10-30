from task_mcp.sources import ReplayBackend, endpoint_url, load_sources, record
from tests.helpers import BASE, gh_backend, gh_list, gh_sources

SRC = gh_sources()


def test_load_example_sources():
    s = load_sources("examples/greenhouse/sources.yaml")
    assert [e["id"] for e in s["endpoints"]] == ["list_jobs", "get_job"]


def test_endpoint_url_fills_path_and_query():
    assert endpoint_url(SRC, "list_jobs", {"board": "acme"}) == (f"{BASE}/boards/acme/jobs", {"content": "true"})


def test_endpoint_url_extra_args_become_params():
    assert endpoint_url(SRC, "get_job", {"board": "acme", "id": 7, "x": 1}) == (f"{BASE}/boards/acme/jobs/7", {"x": "1"})


def test_record_lists_then_details(tmp_path):
    idx = record(SRC, gh_backend(), tmp_path)
    assert [r["endpoint"] for r in idx] == ["list_jobs", "get_job", "get_job"]
    assert (tmp_path / "index.json").exists()
    assert all((tmp_path / r["file"]).exists() for r in idx)


def test_replay_normalizes_int_and_str_ids(tmp_path):  # Review Focus 4
    record(SRC, gh_backend(), tmp_path)
    rb = ReplayBackend(tmp_path)
    jid = gh_list()["jobs"][0]["id"]
    for i in (jid, str(jid)):
        url, params = endpoint_url(SRC, "get_job", {"board": "acme", "id": i})
        status, body = rb.get(url, params)
        assert status == 200 and body["id"] == jid


def test_replay_missing_is_404(tmp_path):
    record(SRC, gh_backend(), tmp_path)
    assert ReplayBackend(tmp_path).get("https://x/y", {})[0] == 404
