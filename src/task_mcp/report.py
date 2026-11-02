"""report: results rows -> REPORT.md."""
import math
import statistics
from collections import Counter

from .arms import ARMS

LABELS = ("pass", "wrong_fit", "missed_flag", "bad_json", "stopped")


def _med(rows, key):
    return statistics.median(r[key] for r in rows) if rows else 0


def _arms(rows):
    present = {r["arm"] for r in rows}
    return [a for a in ARMS if a in present]


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k passes out of n."""
    if not n:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def arm_table(rows):
    lines = ["| Arm | Pass | Pass 95% CI | " + " | ".join(LABELS[1:]) + " | Median tokens in | Median tool chars "
             "| Median calls | Fallback calls | Truncations | Extra flags |", "|---" * (len(LABELS) + 8) + "|"]
    for a in _arms(rows):
        ar = [r for r in rows if r["arm"] == a]
        c = Counter(r["label"] for r in ar)
        k = sum(r["pass"] for r in ar)
        lo, hi = wilson(k, len(ar))
        lines.append(f"| {a} | {k}/{len(ar)} | {lo:.0%}–{hi:.0%} | " + " | ".join(str(c[l]) for l in LABELS[1:])
                     + f" | {_med(ar, 'tokens_in'):.0f} | {_med(ar, 'tool_chars'):.0f} | {_med(ar, 'calls'):.0f}"
                     f" | {sum(r['fallback_calls'] for r in ar)} | {sum(r['truncations'] for r in ar)}"
                     f" | {sum(bool(r.get('extra_flags')) for r in ar)} |")
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


def _by_task(rows, arm):
    return {r["task"]: r for r in rows if r["arm"] == arm}


def caused_mistakes(rows):
    """Tasks raw passed and lean failed: mistakes the trimming caused."""
    raw, lean = _by_task(rows, "raw"), _by_task(rows, "lean")
    return [{"task": t, "raw_label": raw[t]["label"], "lean_label": lean[t]["label"], "lean_final": lean[t]["final"]}
            for t in sorted(raw.keys() & lean.keys()) if raw[t]["pass"] and not lean[t]["pass"]]


def reliability(rows):
    raw, lean = _by_task(rows, "raw"), _by_task(rows, "lean")
    common = sorted(raw.keys() & lean.keys())
    if not common:
        return "No tasks ran in both raw and lean."
    caused = caused_mistakes(rows)
    raw_passed = sum(raw[t]["pass"] for t in common)
    lines = [f"Lean failed {len(caused)} of the {raw_passed} tasks raw passed. These are the mistakes the trimming caused.", ""]
    for c in caused:
        lines += [f"- {c['task']}: raw {c['raw_label']}, lean {c['lean_label']}. lean: `{c['lean_final'][:400]}`"]
    both = [t for t in common if not raw[t]["pass"] and not lean[t]["pass"]]
    wins = [t for t in common if lean[t]["pass"] and not raw[t]["pass"]]
    lines += ["", f"Both failed: {', '.join(both) or 'none'}", f"Lean only: {', '.join(wins) or 'none'}"]
    return "\n".join(lines)


def break_even(rows, stats, agent="agent"):
    """When the one-time extraction pays for itself, in tokens and seconds."""
    raw, lean = _by_task(rows, "raw"), _by_task(rows, "lean")
    common = [t for t in raw.keys() & lean.keys() if raw[t]["pass"] and lean[t]["pass"]]
    n = (stats or {}).get("extracted", 0)
    if not common or not n:
        return "- Break-even: not measured (no common passed tasks or no fresh extractions)."

    def saved(key):
        return _med([raw[t] for t in common], key) - _med([lean[t] for t in common], key)

    def after(cost, save):
        return "never (no saving)" if save <= 0 else f"{cost / save:.1f}"
    s_ex, s_save = stats.get("seconds", 0) / n, saved("seconds")
    ext = stats.get("extract_model", "extractor")
    if not stats.get("tokens_in"):
        return (f"- Extraction per posting: tokens not measured, {s_ex:.0f} s. Saved per query: "
                f"{saved('tokens_in'):.0f} tokens ({agent}), {s_save:.1f} s. Break-even: tokens not measured, "
                f"{after(s_ex, s_save)} queries by seconds.")
    t_ex, t_save = (stats["tokens_in"] + stats.get("tokens_out", 0)) / n, saved("tokens_in")
    return (f"- Extraction per posting: {t_ex:.0f} tokens ({ext}), {s_ex:.0f} s. Saved per query: "
            f"{t_save:.0f} tokens ({agent}), {s_save:.1f} s. Break-even after {after(t_ex, t_save)} queries by "
            f"tokens, {after(s_ex, s_save)} by seconds.")


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
             "lean: shaped plus the plan's drops and extracts. Extra flags: rows whose answer named a flag type "
             "the reference didn't (not failed unless it changed the fit verdict).", "", arm_table(rows), "",
             "## Reliability", "", reliability(rows), "",
             "## Savings", "", "Only on tasks both arms passed, so a cheap failure can't look like a saving.", "",
             *[savings(rows, a, b) for a, b in (("lean", "raw"), ("shaped", "raw"), ("lean", "shaped"))], ""]
    parts += ["## Break-even", "", "One-time extraction cost per posting against tokens and seconds saved per agent "
              "query (medians, tasks both arms passed). Different models, so the token figure is a rough guide.", "",
              break_even(rows, s, meta.get("model", "agent")), ""]
    if s:
        parts += ["## Extraction (one-time precompute)", "",
                  f"{s.get('items', 0)} items: {s.get('extracted', 0)} extracted, {s.get('cached', 0)} cached, "
                  f"{s.get('failed', 0)} failed, {s.get('empty', 0)} empty. {s.get('unverified', 0)} quotes unverified "
                  f"and withheld. {s.get('seconds', 0):.0f}s total.", ""]
    parts += ["## Where lean and raw disagree", "", disagreements(rows)]
    return "\n".join(parts) + "\n"
