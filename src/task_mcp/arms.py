"""The three eval arms, all built from one plan: raw API, task-shaped tools, and shaped + trimmed."""
import copy

from .sources import placeholders

ARMS = ("raw", "shaped", "lean")


def arm_plan(plan, sources, arm):
    if arm == "lean":
        return plan
    if arm == "shaped":
        p = copy.deepcopy(plan)
        p["extracts"] = {}
        for t in p["tools"]:
            t["passthrough"] = True
        return p
    if arm == "raw":
        tools = [{"name": e["id"], "endpoint": e["id"], "passthrough": True,
                  "description": f"GET {e['path']} (raw API response)",
                  "params": {n: {"type": "string", "required": True} for n in placeholders(e["path"])}}
                 for e in sources["endpoints"]]
        return {"api": plan["api"], "task": plan.get("task"), "tools": tools, "extracts": {}}
    raise ValueError(f"unknown arm {arm!r}; use one of {ARMS}")
