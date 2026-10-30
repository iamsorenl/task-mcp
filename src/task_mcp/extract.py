"""Extractor: turn one long text field into the plan's schema, with checked quotes and a disk cache."""
import hashlib
import html
import json
import re
from pathlib import Path

from .fields import html_to_text

SWAPS = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\xa0": " "}


def normalize(s):
    s = html.unescape(html.unescape(s or ""))
    for a, b in SWAPS.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def first_json(text):
    """The first JSON object in text, or raise ValueError."""
    start = (text or "").find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    return json.JSONDecoder().raw_decode(text[start:])[0]


def _prompt(ex, text, error=None):
    fields = []
    for name, spec in ex["schema"].items():
        if spec["type"] == "list" and spec.get("quote"):
            key = "type" if spec.get("enum") else "text"
            shape = f'list of {{"{key}": ..., "quote": exact sentence copied from the text}}'
            if spec.get("enum"):
                shape += f'; type is one of {spec["enum"]}'
        elif spec["type"] == "list":
            shape = "list of short strings"
        else:
            shape = "string or null"
        fields.append(f'- "{name}": {shape}. {spec.get("description", "")}'.rstrip())
    p = (f"{ex.get('instructions', '').strip()}\n\nReply with one JSON object with these keys:\n"
         + "\n".join(fields) + f"\n\nTEXT:\n{text}\n")
    if error:
        p += f"\nYour last reply could not be used ({error}). Reply with only the JSON object.\n"
    return p


def _clean(ex, raw, source):
    """Fill missing keys, move unverifiable quotes to `unverified`, map unknown enum values to other."""
    out, unverified, src = {}, [], normalize(source)
    for name, spec in ex["schema"].items():
        v = raw.get(name)
        if spec["type"] == "list":
            v = v if isinstance(v, list) else []
            if spec.get("quote"):
                kept = []
                for item in v:
                    if not isinstance(item, dict):
                        continue
                    if spec.get("enum") and item.get("type") not in spec["enum"]:
                        item = {**item, "type": "other"}
                    q = normalize(item.get("quote"))
                    if q and q in src:
                        kept.append(item)
                    else:
                        unverified.append({**item, "field": name})
                v = kept
        else:
            v = v if isinstance(v, str) and v.strip() else None
        out[name] = v
    out["unverified"] = unverified
    return out


class Extractor:
    def __init__(self, plan, complete, cache_dir):
        self.extracts = plan.get("extracts") or {}
        self.complete = complete
        self.dir = Path(cache_dir)
        self.last = None  # "cached" | "extracted" | "failed" | "empty", for precompute stats

    def extract(self, name, item_id, value):
        ex = self.extracts[name]
        text = html_to_text(value) if ex.get("html") else str(value or "")
        if not text.strip():
            self.last = "empty"
            return _clean(ex, {}, "")
        digest = hashlib.sha1(text.encode()).hexdigest()[:12]
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(item_id))[:100]  # ids come from API responses
        path = self.dir / name / f"{safe_id}-{digest}.json"
        if path.exists():
            out = json.loads(path.read_text())
            self.last = "failed" if out.get("extract_failed") else "cached"
            return out
        error = None
        for _ in range(2):
            reply = self.complete(_prompt(ex, text, error))
            try:
                out, self.last = _clean(ex, first_json(reply), text), "extracted"
                break
            except ValueError as e:
                error = f"{e}; reply started: {reply[:80]!r}"
        else:
            out, self.last = {"extract_failed": True}, "failed"
        path.parent.mkdir(parents=True, exist_ok=True)  # failures too, so a bad posting isn't retried on every call
        path.write_text(json.dumps(out))
        return out
