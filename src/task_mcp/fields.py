"""Field paths: a small JSONPath subset (`a.b`, `a[*].b`), keep/drop/extract rules, HTML to text."""
import html
import json
import re
from html.parser import HTMLParser

BLOCKS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}


def field_paths(obj, prefix=""):
    """Every leaf path in obj. Array items share one `[*]` path."""
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out += field_paths(v, f"{prefix}.{k}" if prefix else k)
        return list(dict.fromkeys(out))
    if isinstance(obj, list):
        out = []
        for v in obj:
            out += field_paths(v, prefix + "[*]")
        return list(dict.fromkeys(out)) or [prefix + "[*]"]
    return [prefix]


def _parts(path):
    return [p for p in re.split(r"\.|(?=\[\*\])", path) if p]


def get_path(obj, path):
    """Value at path; a list for `[*]` paths; None when missing."""
    parts = _parts(path)

    def walk(o, ps):
        if not ps:
            return o
        p, rest = ps[0], ps[1:]
        if p == "[*]":
            return [walk(x, rest) for x in o] if isinstance(o, list) else None
        return walk(o[p], rest) if isinstance(o, dict) and p in o else None

    return walk(obj, parts)


def _put(src, dst, parts, fn):
    p, rest = parts[0], parts[1:]
    if p == "[*]":
        if not isinstance(src, list):
            return dst
        dst = dst if isinstance(dst, list) else [{} for _ in src]
        for i, x in enumerate(src):
            dst[i] = _put(x, dst[i], rest, fn) if rest else fn(x)
        return dst
    if not isinstance(src, dict) or p not in src:
        return dst
    dst = dst if isinstance(dst, dict) else {}
    dst[p] = _put(src[p], dst.get(p), rest, fn) if rest else fn(src[p])
    return dst


def apply_fields(item, rules, extract_fn=None):
    """New dict holding only `keep` paths, plus extract_fn(name, value) for `{extract: name}` paths."""
    out = {}
    for path, rule in rules.items():
        if rule == "keep":
            fn = lambda v: v
        elif isinstance(rule, dict) and "extract" in rule:
            name = rule["extract"]
            fn = (lambda v, n=name: extract_fn(n, v)) if extract_fn else (lambda v: v)
        else:
            continue
        out = _put(item, out, _parts(path), fn)
    return out


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKS:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in BLOCKS:
            self.out.append("\n")

    def handle_data(self, data):
        self.out.append(data)


def html_to_text(s):
    """HTML (possibly entity-escaped twice, as some APIs send it) to plain text with line breaks."""
    s = html.unescape(s or "")
    if "<" not in s:
        s = html.unescape(s)
    p = _Text()
    p.feed(s)
    text = html.unescape("".join(p.out))
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def est_tokens(x):
    """Rough token estimate, chars/4. Always labeled `est` where shown."""
    return len(x if isinstance(x, str) else json.dumps(x)) // 4
