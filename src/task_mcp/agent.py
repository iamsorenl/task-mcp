"""The tool-calling loop, modeled on mcp-modelcheck's agent.py, plus token usage and truncation."""
import json
import time

SYSTEM = "You are a helpful assistant. Use the tools when they help answer the question."
REPEAT = "blocked: you already made this exact call. Use the earlier result or try something else."
FIELDS_SCHEMA = {"type": "array", "items": {"type": "string"},
                 "description": "Optional: names of dropped fields to return raw, by path."}


def tool_schemas(plan):
    out = []
    for t in plan["tools"]:
        params = t.get("params") or {}
        props = {k: {"type": "string", "description": p.get("description", "")} for k, p in params.items()}
        if not t.get("passthrough"):
            props["fields"] = FIELDS_SCHEMA
        out.append({"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": {"type": "object", "properties": props,
                           "required": [k for k, p in params.items() if p.get("required")]}}})
    return out


def run_task(chat, plan, task, respond, preferences="", max_steps=10, max_tool_chars=60_000, timeout=600):
    """respond(name, args) -> text. chat(messages, tools) -> {content, tool_calls, usage}."""
    schemas = tool_schemas(plan)
    system = SYSTEM + (f"\n\n{preferences.strip()}" if preferences else "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task["q"]}]
    out = {"calls": [], "final": "", "stopped": None, "tokens_in": 0, "tokens_out": 0,
           "truncations": 0, "repeats": 0, "fallback_calls": 0}
    seen, start = set(), time.monotonic()
    try:
        for _ in range(max_steps):
            if time.monotonic() - start > timeout:
                out["stopped"] = "timeout"
                break
            reply = chat(messages, schemas)
            out["tokens_in"] += reply["usage"]["in"]
            out["tokens_out"] += reply["usage"]["out"]
            messages.append({"role": "assistant", "content": reply["content"],
                             "tool_calls": [{"function": {"name": c["name"], "arguments": c["args"]}}
                                            for c in reply["tool_calls"]]})
            if not reply["tool_calls"]:
                out["final"] = reply["content"]
                break
            for c in reply["tool_calls"]:
                key = (c["name"], json.dumps(c["args"], sort_keys=True))
                if key in seen:
                    out["repeats"] += 1
                    text = REPEAT
                else:
                    seen.add(key)
                    text = respond(c["name"], c["args"])
                truncated = len(text) > max_tool_chars
                if truncated:
                    text = text[:max_tool_chars]
                    out["truncations"] += 1
                if c["args"].get("fields"):
                    out["fallback_calls"] += 1
                out["calls"].append({"tool": c["name"], "args": c["args"], "chars": len(text), "truncated": truncated})
                messages.append({"role": "tool", "content": text, "tool_name": c["name"]})
        else:
            out["stopped"] = "step_limit"
    except Exception as e:
        out["stopped"], out["error"] = "error", str(e)
    out["seconds"] = round(time.monotonic() - start, 1)
    return out
