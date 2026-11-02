"""propose: a model drafts plan.yaml from the recordings and a one-line task."""
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

from .fields import est_tokens, field_paths, get_path
from .plan import _items, validate
from .sources import ReplayBackend

MAX_PROMPT = 20_000
MAX_SAMPLES = 3
FORMAT_EXAMPLE = (Path(__file__).parent / "format_example.yaml").read_text()

RULES = """You design a small MCP server for one task, on top of an API whose responses are bloated.
Write a plan.yaml in exactly the format of the example below.
- Propose a few task-shaped tools, not one per endpoint. Typical: a search tool returning short rows, and a detail tool.
- Every field path you list is `keep` or `{extract: <name>}`. Paths you don't list are dropped. Give a reason for big drops under `reasons`.
- Use `extract` for long free text the task needs. Design its schema for the task. Mark lists that need evidence with `quote: true`.
- A param with `filter: <field path>` filters items by a case-insensitive substring match on that field.
- Field paths use `a.b` and `a[*].b`. Use only paths from the inventory.
Reply with only the YAML."""


def _short(v, n):
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + "..."
    if isinstance(v, dict):
        return {k: _short(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [_short(x, n) for x in v[:3]]
    return v


def build_prompt(sources, rec_dir, task, errors=None):
    rb = ReplayBackend(rec_dir)
    parts = [RULES, "EXAMPLE (a made-up API):\n" + FORMAT_EXAMPLE, f"TASK: {task}", f"API: {sources['name']}"]
    samples = []
    for ep in sources["endpoints"]:
        items = [i for b in rb.bodies(ep["id"]) for i in _items(b, ep) if isinstance(i, dict)]
        tokens, example = defaultdict(list), {}
        for item in items[:50]:
            for p in field_paths(item):
                v = get_path(item, p)
                tokens[p].append(est_tokens(v if isinstance(v, str) else json.dumps(v)))
                example.setdefault(p, v)
        params = re.findall(r"{(\w+)}", ep["path"])
        lines = [f"ENDPOINT {ep['id']}: GET {ep['path']}  path params: {params}  "
                 f"{'returns a list at ' + ep['items'] if ep.get('items') else 'returns one item'}  "
                 f"item id field: {ep.get('item_id', 'id')}",
                 "field inventory (path | example | est tokens per item):"]
        lines += [f"  {p} | {json.dumps(_short(example[p], 60))[:80]} | {sum(tokens[p]) // len(tokens[p])}" for p in tokens]
        parts.append("\n".join(lines))
        if items and len(samples) < MAX_SAMPLES:
            samples.append(f"SAMPLE ITEM from {ep['id']}:\n" + json.dumps(_short(items[0], 200)))
    head = "\n\n".join(parts)
    for s in samples:
        if len(head) + len(s) + 2 <= MAX_PROMPT:
            head += "\n\n" + s
    fix = ("\n\nYour last plan had these problems. Fix them:\n" + "\n".join(f"- {e}" for e in errors))[:MAX_PROMPT // 4] \
        if errors else ""
    return head[:MAX_PROMPT - len(fix)] + fix


class ProposeError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def parse_plan(reply):
    m = re.search(r"```(?:ya?ml)?\n(.*?)```", reply, re.S)
    plan = yaml.safe_load(m.group(1) if m else reply)
    if not isinstance(plan, dict):
        raise ValueError("reply is not a YAML mapping")
    return plan


def propose(sources, rec_dir, task, complete):
    errors = None
    for _ in range(2):
        reply = complete(build_prompt(sources, rec_dir, task, errors))
        try:
            plan = parse_plan(reply)
        except (yaml.YAMLError, ValueError) as e:
            errors = [f"could not parse YAML: {str(e)[:200]}"]
            continue
        plan.setdefault("api", sources["name"])
        plan.setdefault("task", task)
        plan.setdefault("sources", "sources.yaml")
        errors = validate(plan, sources, rec_dir)
        if not errors:
            return plan
    raise ProposeError(errors)
