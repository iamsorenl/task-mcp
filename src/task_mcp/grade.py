"""grade: the agent's final answer is JSON with a fit verdict and typed red flags. No judge model."""
from .extract import first_json


def parse_answer(final):
    try:
        v = first_json(final or "")
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def _flag_types(answer):
    flags = answer.get("red_flags") or []
    return {(f.get("type") if isinstance(f, dict) else f) for f in flags if f} - {None}


def grade(task, out):
    exp = task["expected"]
    want = set(exp.get("red_flags") or [])
    result = {"pass": False, "fit_ok": False, "flag_recall": 0.0, "label": "stopped", "extra_flags": []}
    if out.get("stopped") and not out.get("final"):
        return result
    answer = parse_answer(out.get("final"))
    if answer is None or "fit" not in answer:
        return {**result, "label": "bad_json"}
    fit_ok = str(answer["fit"]).strip().lower() == str(exp["fit"]).strip().lower()
    recall = len(want & _flag_types(answer)) / len(want) if want else 1.0
    label = "wrong_fit" if not fit_ok else "missed_flag" if recall < 1.0 else "pass"
    return {"pass": label == "pass", "fit_ok": fit_ok, "flag_recall": round(recall, 3), "label": label,
            "extra_flags": sorted(map(str, _flag_types(answer) - want))}
