"""Record detail calls for chosen items (the eval's task set), on top of `task-mcp record`.
Usage: uv run python scripts/record_ids.py <api dir> <endpoint id> key=value,key=value ..."""
import json
import sys
from pathlib import Path

from task_mcp.sources import LiveBackend, endpoint_url, load_sources, request_key

d, ep = Path(sys.argv[1]), sys.argv[2]
src, rec = load_sources(d / "sources.yaml"), d / "recordings"
idx = json.loads((rec / "index.json").read_text())
have = {r["key"] for r in idx}
for spec in sys.argv[3:]:
    args = dict(kv.split("=", 1) for kv in spec.split(","))
    url, params = endpoint_url(src, ep, args)
    key = request_key(url, params)
    if key in have:
        continue
    status, body = LiveBackend().get(url, params)
    (rec / f"{key}.json").write_text(json.dumps(body))
    idx.append({"key": key, "endpoint": ep, "url": url, "params": params, "file": f"{key}.json", "status": status})
    have.add(key)
    print(status, url)
(rec / "index.json").write_text(json.dumps(idx, indent=1))
