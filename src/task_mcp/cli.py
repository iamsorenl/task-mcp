"""task-mcp CLI. An API folder holds sources.yaml, plan.yaml and tasks.yaml; outputs go next to them."""
import argparse
import datetime
import json
import sys
from pathlib import Path

import yaml

from . import build as build_mod
from .agent import run_task
from .arms import ARMS, arm_plan
from .extract import Extractor
from .grade import grade
from .plan import load_plan, summary, validate
from .propose import ProposeError, propose
from .providers import claude_code_complete, ollama_chat, ollama_complete
from .report import render
from .runtime import call_tool, precompute
from .sources import LiveBackend, ReplayBackend, load_sources, record

AGENT_MODEL, EXTRACT_MODEL = "gpt-oss:20b", "gemma4:12b"
CHAT_FACTORY = ollama_chat


def COMPLETE_FACTORY(provider, model, json_mode=False):
    if provider == "claude-code":
        return claude_code_complete(model)
    if json_mode:  # extraction: short structured answers, no thinking
        return ollama_complete(model or EXTRACT_MODEL, num_ctx=16384, json_mode=True, think=False, max_out=1500)
    return ollama_complete(model or AGENT_MODEL)


def _paths(d):
    d = Path(d)
    return d, load_sources(d / "sources.yaml"), d / "recordings"


def _valid_plan(d, src, rec):
    """-> plan, or None after printing why it is invalid."""
    plan = load_plan(d / "plan.yaml")
    errs = validate(plan, src, rec if rec.exists() else None)
    if errs:
        print("\n".join(f"ERROR: {e}" for e in errs), file=sys.stderr)
        return None
    return plan


def cmd_record(a):
    d, src, rec = _paths(a.dir)
    idx = record(src, LiveBackend(), rec)
    print(f"recorded {len(idx)} calls to {rec}")
    return 0


def cmd_propose(a):
    d, src, rec = _paths(a.dir)
    try:
        plan = propose(src, rec, a.task, COMPLETE_FACTORY(a.provider, a.model))
    except ProposeError as e:
        print("propose failed after a retry:\n" + "\n".join(f"- {x}" for x in e.errors), file=sys.stderr)
        return 1
    out = d / "plan.proposed.yaml"
    out.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))
    print(f"wrote {out}. Review it with: task-mcp review {d} --plan plan.proposed.yaml")
    return 0


def cmd_review(a):
    d, src, rec = _paths(a.dir)
    plan = load_plan(d / a.plan)
    if not rec.exists():
        errs = validate(plan, src)
        print("no recordings yet, so only the plan's shape was checked. Run: task-mcp record " + str(d))
    else:
        errs = validate(plan, src, rec)
        print(summary(plan, src, rec) if not errs else "")
    for e in errs:
        print(f"ERROR: {e}")
    return 1 if errs else 0


def cmd_build(a):
    d, src, rec = _paths(a.dir)
    if _valid_plan(d, src, rec) is None:
        return 1
    print(f"built {build_mod.build(d / 'plan.yaml', a.out)}")
    return 0


def _extractor(d, plan, a):
    return Extractor(plan, COMPLETE_FACTORY("ollama", a.extract_model, json_mode=True), d / "cache")


def cmd_precompute(a):
    d, src, rec = _paths(a.dir)
    plan = _valid_plan(d, src, rec)
    if plan is None:
        return 1
    stats = {**precompute(plan, src, ReplayBackend(rec), _extractor(d, plan, a)), "extract_model": a.extract_model}
    (d / "runs").mkdir(exist_ok=True)
    (d / "runs" / "precompute.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats))
    return 0


def _save_rows(path, rows, task_ids):
    key = lambda r: (r["arm"], r["model"], r["task"])
    done = {key(r) for r in rows}
    keep = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    keep = [r for r in keep if key(r) not in done and r["task"] in task_ids]
    path.write_text("".join(json.dumps(r) + "\n" for r in keep + rows))


def cmd_eval(a):
    d, src, rec = _paths(a.dir)
    plan = _valid_plan(d, src, rec)
    if plan is None:
        return 1
    tasks_doc, rb = yaml.safe_load((d / "tasks.yaml").read_text()), ReplayBackend(rec)
    tasks = [t for t in tasks_doc["tasks"] if t.get("checked") or not a.only_checked]
    task_ids = {t["id"] for t in tasks}
    if a.tasks:
        want = a.tasks.split(",")
        if unknown := sorted(set(want) - {t["id"] for t in tasks}):
            print(f"unknown or unchecked task ids: {unknown}", file=sys.stderr)
            return 1
        tasks = [t for t in tasks if t["id"] in want]
    chat, rows = CHAT_FACTORY(a.model), []
    for arm in a.arms.split(","):
        p = arm_plan(plan, src, arm)
        ex = _extractor(d, plan, a) if arm == "lean" else None
        respond = lambda n, args, p=p, ex=ex: json.dumps(call_tool(p, src, n, args, rb, ex))
        for t in tasks:
            out = run_task(chat, p, t, respond, preferences=tasks_doc.get("preferences", ""))
            g = grade(t, out)
            rows.append({"arm": arm, "model": a.model, "task": t["id"], **g,
                         "tokens_in": out["tokens_in"], "tokens_out": out["tokens_out"],
                         "tool_chars": sum(c["chars"] for c in out["calls"]), "calls": len(out["calls"]),
                         "fallback_calls": out["fallback_calls"], "truncations": out["truncations"],
                         "seconds": out["seconds"], "final": out["final"], "stopped": out["stopped"]})
            print(f"{arm} {t['id']}: {g['label']} ({out['tokens_in']} tokens in)", flush=True)
    (d / "runs").mkdir(exist_ok=True)
    _save_rows(d / "runs" / "results.jsonl", rows, task_ids)
    return 0


def _latest_extracts(d, task_ids):
    """task id -> newest cached extract for its item (the id after the last '-'), for the report's Reliability notes."""
    out = {}
    for t in task_ids:
        files = sorted(Path(d, "cache").glob(f"*/{t.rsplit('-', 1)[-1]}-*.json"), key=lambda f: f.stat().st_mtime)
        if files:
            out[t] = json.loads(files[-1].read_text())
    return out


def cmd_report(a):
    d = Path(a.dir)
    rows = [json.loads(l) for l in (d / "runs" / "results.jsonl").read_text().splitlines()]
    pre = d / "runs" / "precompute.json"
    stats = json.loads(pre.read_text()) if pre.exists() else {}
    models = sorted({r["model"] for r in rows})
    if a.model:
        rows = [r for r in rows if r["model"] == a.model]
    elif len(models) > 1:
        print(f"results.jsonl holds several agent models {models}; pick one with --model", file=sys.stderr)
        return 1
    if not rows:
        print(f"no results for model {a.model}", file=sys.stderr)
        return 1
    meta = {"api": d.name, "model": a.model or models[0], "date": datetime.date.today().isoformat()}
    extracts = _latest_extracts(d, sorted({r["task"] for r in rows}))
    (d / "REPORT.md").write_text(render(rows, stats, meta, extracts))
    print(f"wrote {d / 'REPORT.md'}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="task-mcp", description="Generate lean, task-specific MCP servers from bloated APIs.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("record", help="call the API and save responses")
    s.add_argument("dir")
    s.set_defaults(fn=cmd_record)
    s = sub.add_parser("propose", help="draft plan.proposed.yaml with a model")
    s.add_argument("dir")
    s.add_argument("--task", required=True)
    s.add_argument("--provider", choices=["ollama", "claude-code"], default="ollama")
    s.add_argument("--model", default=None)
    s.set_defaults(fn=cmd_propose)
    s = sub.add_parser("review", help="print what a plan keeps, extracts and drops")
    s.add_argument("dir")
    s.add_argument("--plan", default="plan.yaml")
    s.set_defaults(fn=cmd_review)
    s = sub.add_parser("build", help="generate the MCP server")
    s.add_argument("dir")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_build)
    for name, fn, help_ in (("precompute", cmd_precompute, "extract every recorded item once"),
                            ("eval", cmd_eval, "compare raw, shaped and lean on the tasks")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("dir")
        s.add_argument("--extract-model", default=EXTRACT_MODEL)
        s.set_defaults(fn=fn)
        if name == "eval":
            s.add_argument("--arms", default=",".join(ARMS))
            s.add_argument("--model", default=AGENT_MODEL)
            s.add_argument("--only-checked", action="store_true")
            s.add_argument("--tasks", default=None, help="comma-separated task ids; other rows are kept")
    s = sub.add_parser("report", help="write REPORT.md from eval results")
    s.add_argument("dir")
    s.add_argument("--model", default=None, help="agent model to report on, when results hold more than one")
    s.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
