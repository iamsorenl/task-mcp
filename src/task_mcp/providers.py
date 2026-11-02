"""Model providers. Ollama is the default; claude-code runs on the user's own Claude Code login."""
import json
import subprocess
import tempfile

import ollama


def ollama_complete(model, num_ctx=32768, json_mode=False, think=None, max_out=None, client=None):
    """think=False stops thinking models (e.g. gemma4) spending the whole output budget before answering."""
    client = client or ollama.Client(timeout=600)
    options = {"temperature": 0, "num_ctx": num_ctx, **({"num_predict": max_out} if max_out else {})}
    extra = {**({"format": "json"} if json_mode else {}), **({"think": think} if think is not None else {})}

    def complete(prompt):
        r = client.chat(model=model, messages=[{"role": "user", "content": prompt}], options=options, **extra)
        complete.usage = {"in": r.prompt_eval_count or 0, "out": r.eval_count or 0}
        return r.message.content or ""
    return complete


def claude_code_complete(model=None):
    """Shells out to `claude -p`. Uses whatever login Claude Code has; never asks for one itself."""
    def complete(prompt):
        # The prompt carries untrusted API text, so Claude gets no tools, no MCP servers, and an empty folder.
        cmd = ["claude", "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
               "--setting-sources", "",
               *(["--model", model] if model else [])]
        with tempfile.TemporaryDirectory() as empty:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=empty)
        if r.returncode != 0:
            raise RuntimeError(f"claude -p failed: {(r.stderr or r.stdout).strip()[:500]}")
        out = json.loads(r.stdout)
        if out.get("is_error"):  # e.g. usage limit hit: exit 0, error text in result
            raise RuntimeError(f"claude -p failed: {str(out.get('result'))[:500]}")
        return out["result"]
    return complete


def ollama_chat(model, num_ctx=32768, client=None):
    """-> chat(messages, tools) returning content, tool_calls, and token usage from Ollama."""
    client = client or ollama.Client(timeout=600)

    def chat(messages, tools):
        r = client.chat(model=model, messages=messages, tools=tools, options={"temperature": 0, "num_ctx": num_ctx})
        m = r.message
        return {"content": m.content or "",
                "tool_calls": [{"name": c.function.name, "args": dict(c.function.arguments or {})}
                               for c in m.tool_calls or []],
                "usage": {"in": r.prompt_eval_count or 0, "out": r.eval_count or 0}}
    return chat
