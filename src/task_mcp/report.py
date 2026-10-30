"""report: results rows -> REPORT.md."""
import statistics
from collections import Counter

from .arms import ARMS

LABELS = ("pass", "wrong_fit", "missed_flag", "bad_json", "stopped")


def _med(rows, key):
    return statistics.median(r[key] for r in rows) if rows else 0


def _arms(rows):
    present = {r["arm"] for r in rows}
    return [a for a in ARMS if a in present]


def arm_table(rows):
    lines = ["| Arm | Pass | " + " | ".join(LABELS[1:]) + " | Median tokens in | Median tool chars | Median calls "
             "| Fallback calls | Truncations |", "|---" * (len(LABELS) + 6) + "|"]
    for a in _arms(rows):
        ar = [r for r in rows if r["arm"] == a]
        c = Counter(r["label"] for r in ar)
        lines.append(f"| {a} | {sum(r['pass'] for r in ar)}/{len(ar)} | " + " | ".join(str(c[l]) for l in LABELS[1:])
                     + f" | {_med(ar, 'tokens_in'):.0f} | {_med(ar, 'tool_chars'):.0f} | {_med(ar, 'calls'):.0f}"
                     f" | {sum(r['fallback_calls'] for r in ar)} | {sum(r['truncations'] for r in ar)} |")
    return "\n".join(lines)


def savings(rows, a, b):
    """a vs b, only on tasks both arms passed."""
    pa = {r["task"]: r for r in rows if r["arm"] == a and r["pass"]}
    pb = {r["task"]: r for r in rows if r["arm"] == b and r["pass"]}
    common = sorted(pa.keys() & pb.keys())
    if not common:
        return f"- {a} vs {b}: no common passed tasks"
    ta, tb = _med([pa[t] for t in common], "tokens_in"), _med([pb[t] for t in common], "tokens_in")
    ratio = f"{tb / ta:.1f}x fewer" if ta and ta < tb else "no saving"
    return f"- {a} vs {b} (n={len(common)}): median tokens in {tb:.0f} -> {ta:.0f} ({ratio})"


def disagreements(rows, n=5):
    lean = {r["task"]: r for r in rows if r["arm"] == "lean"}
    raw = {r["task"]: r for r in rows if r["arm"] == "raw"}
    out = []
    for t in sorted(lean.keys() & raw.keys()):
        if lean[t]["label"] != raw[t]["label"]:
            out += [f"### {t}: raw {raw[t]['label']}, lean {lean[t]['label']}",
                    f"- raw: `{raw[t]['final'][:400]}`", f"- lean: `{lean[t]['final'][:400]}`", ""]
        if len(out) >= n * 4:
            break
    return "\n".join(out) or "None."


def render(rows, precompute_stats, meta):
    s = precompute_stats or {}
    parts = [f"# Results: {meta.get('api', '')}", "",
             f"Agent model `{meta.get('model')}`, run {meta.get('date')}. Token counts are Ollama's own "
             "(`prompt_eval_count`, summed over every turn of a task). Tool chars are characters of tool results "
             "the model saw, after truncation.", "",
             "## By arm", "",
             "raw: the API as is, one tool per endpoint. shaped: the plan's task-shaped tools, every field kept. "
             "lean: shaped plus the plan's drops and extracts.", "", arm_table(rows), "",
             "## Savings", "", "Only on tasks both arms passed, so a cheap failure can't look like a saving.", "",
             *[savings(rows, a, b) for a, b in (("lean", "raw"), ("shaped", "raw"), ("lean", "shaped"))], ""]
    if s:
        parts += ["## Extraction (one-time precompute)", "",
                  f"{s.get('items', 0)} items: {s.get('extracted', 0)} extracted, {s.get('cached', 0)} cached, "
                  f"{s.get('failed', 0)} failed, {s.get('empty', 0)} empty. {s.get('unverified', 0)} quotes unverified "
                  f"and withheld. {s.get('seconds', 0):.0f}s total.", ""]
    parts += ["## Where lean and raw disagree", "", disagreements(rows)]
    return "\n".join(parts) + "\n"
