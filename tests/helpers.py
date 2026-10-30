import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
BASE = "https://boards-api.greenhouse.io/v1"


def gh_list():
    return json.loads((FIX / "gh_list.json").read_text())


class FakeBackend:
    """Answers GETs from a dict keyed by url; params are ignored."""
    def __init__(self, by_url):
        self.by_url, self.seen = by_url, []

    def get(self, url, params):
        self.seen.append((url, params))
        return (200, self.by_url[url]) if url in self.by_url else (404, {"error": "not found"})


def gh_backend():
    lst = gh_list()
    by = {f"{BASE}/boards/acme/jobs": lst}
    for j in lst["jobs"]:
        by[f"{BASE}/boards/acme/jobs/{j['id']}"] = j
    return FakeBackend(by)


def gh_sources(max_details=2):
    return {"name": "greenhouse", "base": BASE,
            "endpoints": [{"id": "list_jobs", "path": "/boards/{board}/jobs", "query": {"content": "true"},
                           "items": "jobs[*]", "item_id": "id"},
                          {"id": "get_job", "path": "/boards/{board}/jobs/{id}", "item_id": "id",
                           "detail_of": "list_jobs"}],
            "seeds": {"board": ["acme"]}, "max_details": max_details}
