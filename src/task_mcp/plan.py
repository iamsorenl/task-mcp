"""plan.yaml: load, validate, estimate token savings, and the readable summary `review` prints."""
import builtins
import keyword
from pathlib import Path

import yaml

from .fields import apply_fields, est_tokens, field_paths, get_path
from .sources import ReplayBackend, endpoint, placeholders

RULES = ("keep",)
TYPES = ("string", "list")
EXTRACT_EST = 300  # est tokens an extract adds to a response
# Globals of the generated server.py (build.HEADER); a tool with one of these names would shadow it.
SERVER_GLOBALS = {"json", "os", "Path", "Annotated", "MCPServer", "ToolAnnotations", "Field", "Extractor", "load_plan",
                  "ollama_complete", "call_tool", "LiveBackend", "load_sources", "HERE", "PLAN", "SRC", "EXTRACTOR",
                  "BACKEND", "LOG", "READ_ONLY", "FIELDS_DOC", "server", "_call"}


def load_plan(path):
    path = Path(path)
    plan = yaml.safe_load(path.read_text())
    plan["sources_path"] = str(path.parent / plan["sources"])
    return plan


def _items(body, ep):
    if ep.get("items"):
        return get_path(body, ep["items"]) or []
    return [body]


def _recorded_paths(sources, rec_dir, endpoint_id):
    ep = endpoint(sources, endpoint_id)
    paths = set()
    for body in ReplayBackend(rec_dir).bodies(endpoint_id):
        for item in _items(body, ep):
            paths.update(field_paths(item))
    return paths


def _is_map_of_maps(x):
    return isinstance(x, dict) and all(isinstance(v, dict) for v in x.values())


def _shape_errors(plan):
    """Model-written YAML can parse yet have the wrong shape; catch that before anything calls .get() on it."""
    tools, extracts = plan.get("tools") or [], plan.get("extracts") or {}
    if not isinstance(tools, list) or not all(isinstance(t, dict) for t in tools):
        return ["tools must be a list of mappings"]
    errs = [] if _is_map_of_maps(extracts) else ["extracts must map each name to a mapping"]
    if not errs:
        errs += [f"extract {n}: schema must map each field to a mapping like {{type: string}}"
                 for n, ex in extracts.items() if not _is_map_of_maps(ex.get("schema") or {})]
    for t in tools:
        if not _is_map_of_maps(t.get("params") or {}):
            errs.append(f"tool {t.get('name')}: params must map each name to a mapping like {{type: string}}")
        if not isinstance(t.get("fields") or {}, dict):
            errs.append(f"tool {t.get('name')}: fields must map each path to keep or {{extract: name}}")
    return errs


def _bad_name(n, tool=False):
    """Names end up in file paths and generated Python."""
    n = str(n)
    if not n.isidentifier() or keyword.iskeyword(n):
        return "must be a plain identifier and not a Python keyword"
    if tool and (n in SERVER_GLOBALS or hasattr(builtins, n)):
        return "is reserved by the generated server"
    if not tool and n == "fields":
        return "is reserved for the fallback param"


def validate(plan, sources, rec_dir=None):
    """-> list of error strings; empty means the plan can be built."""
    errs = _shape_errors(plan)
    if errs:
        return errs
    known = {e["id"] for e in sources["endpoints"]}
    extracts = plan.get("extracts") or {}
    for n in extracts:
        if why := _bad_name(n):
            errs.append(f"extract name {n!r} {why}")
    for t in plan.get("tools") or []:
        if why := _bad_name(t.get("name"), tool=True):
            errs.append(f"tool name {t.get('name')!r} {why}")
        for n in t.get("params") or {}:
            if why := _bad_name(n):
                errs.append(f"tool {t.get('name')}: param name {n!r} {why}")
    for name, ex in extracts.items():
        for field, spec in (ex.get("schema") or {}).items():
            if spec.get("type") not in TYPES:
                errs.append(f"extract {name}.{field}: type {spec.get('type')!r} must be one of {TYPES}")
    for t in plan.get("tools") or []:
        where = f"tool {t.get('name')}"
        if t.get("endpoint") not in known:
            errs.append(f"{where}: unknown endpoint {t.get('endpoint')!r}")
            continue
        params = t.get("params") or {}
        errs += [f"{where}: path placeholder {n!r} must be a required param"
                 for n in placeholders(endpoint(sources, t["endpoint"])["path"])
                 if not params.get(n, {}).get("required")]
        for path, rule in (t.get("fields") or {}).items():
            if rule in RULES:
                continue
            if isinstance(rule, dict) and "extract" in rule:
                if rule["extract"] not in extracts:
                    errs.append(f"{where}: field {path} uses unknown extract {rule['extract']!r}")
                continue
            errs.append(f"{where}: field {path} has rule {rule!r}; use keep or {{extract: name}}")
        if rec_dir:
            seen = _recorded_paths(sources, rec_dir, t["endpoint"])
            for pname, p in (t.get("params") or {}).items():
                if p.get("filter") and p["filter"] not in seen:
                    errs.append(f"{where}: param {pname} filters on {p['filter']!r}, not in recorded items")
    if not plan.get("tools"):
        errs.append("plan has no tools")
    return errs


def shaped_response(t, ep, body, extract_fn=None):
    """What a tool returns for one raw body, before filters."""
    items = [apply_fields(i, t.get("fields") or {}, extract_fn) for i in _items(body, ep)]
    return {"items": items, "count": len(items)} if ep.get("items") else items[0]


def estimate(plan, sources, rec_dir):
    """-> {tool: {"before": est tokens, "after": est tokens}}, averaged over recordings."""
    out, fake = {}, (lambda name, v: "x" * EXTRACT_EST * 4)
    for t in plan["tools"]:
        ep = endpoint(sources, t["endpoint"])
        bodies = ReplayBackend(rec_dir).bodies(t["endpoint"])
        if not bodies:
            out[t["name"]] = {"before": 0, "after": 0}
            continue
        before = sum(est_tokens(b) for b in bodies) // len(bodies)
        after = sum(est_tokens(shaped_response(t, ep, b, fake)) for b in bodies) // len(bodies)
        out[t["name"]] = {"before": before, "after": after}
    return out


def summary(plan, sources, rec_dir):
    est = estimate(plan, sources, rec_dir)
    lines = [f"Plan for {plan['api']}: {plan.get('task', '')}", ""]
    for t in plan["tools"]:
        fields = t.get("fields") or {}
        seen = sorted(_recorded_paths(sources, rec_dir, t["endpoint"]))
        kept = [p for p, r in fields.items() if r == "keep"]
        extracted = [f"{p} -> extract {r['extract']}" for p, r in fields.items() if isinstance(r, dict)]
        covered = lambda p: any(p == f or p.startswith(f + ".") or p.startswith(f + "[*]") for f in fields)
        dropped = [p for p in seen if not covered(p)]
        reasons = t.get("reasons") or {}
        e = est[t["name"]]
        lines += [f"## {t['name']}  ({t['endpoint']})  est tokens/call: {e['before']} -> {e['after']}",
                  f"  {t.get('description', '')}",
                  "  params: " + ", ".join(f"{k}{' (filter ' + v['filter'] + ')' if v.get('filter') else ''}"
                                           for k, v in (t.get("params") or {}).items()),
                  "  keep: " + ", ".join(kept)]
        lines += [f"  {x}" for x in extracted]
        lines.append(f"  dropped ({len(dropped)}):")
        for p in dropped:
            top = p.split(".")[0].split("[")[0]
            why = reasons.get(p) or reasons.get(top)
            lines.append(f"    - {p}" + (f": {why}" if why else ""))
        lines.append("")
    return "\n".join(lines)
