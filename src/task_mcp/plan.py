"""plan.yaml: load, validate, estimate token savings, and the readable summary `review` prints."""
from pathlib import Path

import yaml

from .fields import apply_fields, est_tokens, field_paths, get_path
from .sources import ReplayBackend, endpoint

RULES = ("keep",)
TYPES = ("string", "list")
EXTRACT_EST = 300  # est tokens an extract adds to a response


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


def validate(plan, sources, rec_dir=None):
    """-> list of error strings; empty means the plan can be built."""
    errs, known = [], {e["id"] for e in sources["endpoints"]}
    extracts = plan.get("extracts") or {}
    for name, ex in extracts.items():
        for field, spec in (ex.get("schema") or {}).items():
            if spec.get("type") not in TYPES:
                errs.append(f"extract {name}.{field}: type {spec.get('type')!r} must be one of {TYPES}")
    for t in plan.get("tools") or []:
        where = f"tool {t.get('name')}"
        if t.get("endpoint") not in known:
            errs.append(f"{where}: unknown endpoint {t.get('endpoint')!r}")
            continue
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
