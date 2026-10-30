"""call_tool: what a generated server does for one tool call. Shared by the live server and the eval."""
import datetime
import json

from .fields import apply_fields, get_path, html_to_text
from .plan import _items
from .sources import endpoint, endpoint_url, placeholders


def find_tool(plan, name):
    return next((t for t in plan["tools"] if t["name"] == name), None)


def _matches(item, path, needle):
    v = get_path(item, path)
    text = " ".join(map(str, v)) if isinstance(v, list) else str(v or "")
    return needle.lower() in text.lower()


def _log(log_path, tool, path, item_id):
    with open(log_path, "a") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                            "tool": tool, "path": path, "item_id": item_id}) + "\n")


def call_tool(plan, sources, name, args, backend, extractor=None, log_path=None):
    t = find_tool(plan, name)
    if not t:
        return {"error": f"unknown tool: {name}"}
    args = {k: v for k, v in (args or {}).items() if v is not None}
    want = args.pop("fields", None) or []
    want = [want] if isinstance(want, str) else list(want)
    params = t.get("params") or {}
    missing = [k for k, p in params.items() if p.get("required") and k not in args]
    if missing:
        return {"error": f"missing required param: {', '.join(missing)}"}

    ep = endpoint(sources, t["endpoint"])
    filters = {k: str(args[k]) for k, p in params.items() if p.get("filter") and k in args}
    call_args = {k: v for k, v in args.items() if k not in filters and (k in params or k in placeholders(ep["path"]))}
    url, query = endpoint_url(sources, t["endpoint"], call_args)
    status, body = backend.get(url, query)
    if status >= 400:
        return {"error": f"HTTP {status}: {json.dumps(body)[:300]}"}

    extracts = plan.get("extracts") or {}
    out = []
    for item in _items(body, ep):
        if not isinstance(item, dict):
            continue
        if not all(_matches(item, params[k]["filter"], v) for k, v in filters.items()):
            continue
        item_id = str(item.get(ep.get("item_id", "id")))

        def extract_fn(ex_name, value, item_id=item_id):
            if extractor:
                return extractor.extract(ex_name, item_id, value)
            return html_to_text(value) if extracts.get(ex_name, {}).get("html") else value

        shaped = apply_fields(item, t.get("fields") or {}, extract_fn)
        if want:
            shaped["_fields"] = {p: get_path(item, p) for p in want}
            if log_path:
                for p in want:
                    _log(log_path, name, p, item_id)
        out.append(shaped)
    if ep.get("items"):
        return {"items": out, "count": len(out)}
    return out[0] if out else {"error": "empty response"}
