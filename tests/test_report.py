from task_mcp.report import render

META = {"model": "gpt-oss:20b", "date": "2026-10-30", "api": "greenhouse"}


def row(arm, task, ok, tokens, label=None, final="{}"):
    return {"arm": arm, "task": task, "pass": ok, "label": label or ("pass" if ok else "wrong_fit"),
            "tokens_in": tokens, "tokens_out": 10, "tool_chars": tokens * 4, "calls": 2,
            "fallback_calls": 0, "truncations": 0, "seconds": 1.0, "final": final}


ROWS = [row("raw", "t1", True, 1000), row("raw", "t2", False, 1000, final='{"fit":"yes"}'),
        row("lean", "t1", True, 250), row("lean", "t2", True, 250, final='{"fit":"no"}')]


def test_table_has_each_arm():
    md = render(ROWS, {}, META)
    assert "| raw | 1/2 |" in md and "| lean | 2/2 |" in md


def test_savings_only_on_common_passes():
    md = render(ROWS, {}, META)
    assert "lean vs raw (n=1)" in md and "1000 -> 250" in md


def test_no_common_passes_message():
    rows = [row("raw", "t1", True, 1000), row("lean", "t2", True, 250)]
    assert "no common passed tasks" in render(rows, {}, META)


def test_disagreements_quote_both_finals():
    md = render(ROWS, {}, META)
    assert "t2" in md and '{"fit":"yes"}' in md and '{"fit":"no"}' in md


def test_extraction_section_and_token_label():
    md = render(ROWS, {"items": 20, "extracted": 20, "cached": 0, "failed": 0, "empty": 0, "unverified": 3, "seconds": 600.0}, META)
    assert "unverified" in md and "Ollama" in md
