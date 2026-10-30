"""Sources: which endpoints an API has, how to call them live or from recordings, and record()."""
import hashlib
import itertools
import json
import re
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

from .fields import get_path


def load_sources(path):
    return yaml.safe_load(Path(path).read_text())


def endpoint(sources, endpoint_id):
    for e in sources["endpoints"]:
        if e["id"] == endpoint_id:
            return e
    raise KeyError(f"unknown endpoint: {endpoint_id}")


def placeholders(path):
    return re.findall(r"{(\w+)}", path)


def endpoint_url(sources, endpoint_id, args):
    """-> (url, params). Path placeholders come from args; other args plus the endpoint query become params."""
    e = endpoint(sources, endpoint_id)
    names = placeholders(e["path"])
    path = e["path"].format(**{n: quote(str(args[n]), safe="") for n in names})  # args may come from the agent
    params = {k: str(v) for k, v in (e.get("query") or {}).items()}
    params.update({k: str(v) for k, v in args.items() if k not in names})
    return sources["base"].rstrip("/") + path, params


def request_key(url, params):
    """Same key for int and str values: everything is str()'d and sorted."""
    norm = json.dumps([url, sorted((k, str(v)) for k, v in params.items())])
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


class LiveBackend:
    def __init__(self, timeout=30):
        self.timeout = timeout

    def get(self, url, params):
        r = httpx.get(url, params=params, timeout=self.timeout, follow_redirects=True)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"error": r.text[:500]}


class ReplayBackend:
    """Answers from recordings on disk. Nothing goes over the network."""
    def __init__(self, rec_dir):
        self.dir = Path(rec_dir)
        self.index = {r["key"]: r for r in json.loads((self.dir / "index.json").read_text())}

    def get(self, url, params):
        r = self.index.get(request_key(url, params))
        if not r:
            return 404, {"error": "not recorded"}
        return r["status"], json.loads((self.dir / r["file"]).read_text())

    def bodies(self, endpoint_id):
        """Every recorded body for one endpoint, in recording order."""
        return [json.loads((self.dir / r["file"]).read_text())
                for r in self.index.values() if r["endpoint"] == endpoint_id and r["status"] < 400]


def _save(out, idx, endpoint_id, url, params, status, body):
    key = request_key(url, params)
    (out / f"{key}.json").write_text(json.dumps(body))
    idx.append({"key": key, "endpoint": endpoint_id, "url": url, "params": params,
                "file": f"{key}.json", "status": status})


def record(sources, backend, out_dir):
    """Call every non-detail endpoint once per seed combination, then the first max_details items' details."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = sources.get("seeds") or {}
    combos = [dict(zip(seeds, vals)) for vals in itertools.product(*seeds.values())] or [{}]
    idx = []
    for args in combos:
        for e in sources["endpoints"]:
            if e.get("detail_of"):
                continue
            url, params = endpoint_url(sources, e["id"], args)
            status, body = backend.get(url, params)
            _save(out, idx, e["id"], url, params, status, body)
            for d in (x for x in sources["endpoints"] if x.get("detail_of") == e["id"]):
                items = get_path(body, e["items"]) if e.get("items") and status < 400 else []
                for item in (items or [])[: sources.get("max_details", 10)]:
                    dargs = {**args, d.get("item_id", "id"): item[e.get("item_id", "id")]}
                    durl, dparams = endpoint_url(sources, d["id"], dargs)
                    dstatus, dbody = backend.get(durl, dparams)
                    _save(out, idx, d["id"], durl, dparams, dstatus, dbody)
    (out / "index.json").write_text(json.dumps(idx, indent=1))
    return idx
