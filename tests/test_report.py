from task_mcp.report import break_even, caused_mistakes, render, wilson

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


def test_wilson_known_value():
    lo, hi = wilson(17, 20)
    assert round(lo, 3) == 0.640 and round(hi, 3) == 0.948
    assert wilson(0, 0) == (0.0, 0.0)


def test_caused_mistakes_only_raw_pass_lean_fail():
    rows = [row("raw", "t1", True, 1000), row("lean", "t1", False, 250, label="missed_flag"),
            row("raw", "t2", False, 1000), row("lean", "t2", False, 250),
            row("raw", "t3", False, 1000), row("lean", "t3", True, 250)]
    assert [(c["task"], c["raw_label"], c["lean_label"]) for c in caused_mistakes(rows)] == [("t1", "pass", "missed_flag")]


def test_reliability_section_lists_caused_both_fail_and_lean_wins():
    rows = [row("raw", "t1", True, 1000), row("lean", "t1", False, 250, label="missed_flag", final="LEANFINAL"),
            row("raw", "t2", False, 1000), row("lean", "t2", False, 250),
            row("raw", "t3", False, 1000), row("lean", "t3", True, 250)]
    md = render(rows, {}, META)
    assert "## Reliability" in md and "failed 1 of the 1 tasks raw passed" in md and "LEANFINAL" in md
    assert "Both failed: t2" in md and "Lean only: t3" in md


def test_break_even_handles_missing_token_stats():  # Review Focus 5
    assert "not measured" in break_even(ROWS, {"items": 50, "extracted": 50, "seconds": 2004.4})


def test_break_even_numbers():
    rows = [row("raw", "t1", True, 1000), row("lean", "t1", True, 250)]
    rows[0]["seconds"], rows[1]["seconds"] = 10.0, 6.0
    md = break_even(rows, {"extracted": 10, "seconds": 400.0, "tokens_in": 20000, "tokens_out": 5000,
                           "extract_model": "gemma4:12b"}, agent="gpt-oss:20b")
    assert "2500 tokens (gemma4:12b)" in md and "40 s" in md and "750 tokens (gpt-oss:20b)" in md
    assert "3.3 queries by tokens" in md and "10.0 by seconds" in md


def test_break_even_no_saving():
    rows = [row("raw", "t1", True, 250), row("lean", "t1", True, 1000)]
    assert "never (no saving)" in break_even(rows, {"extracted": 1, "seconds": 1.0, "tokens_in": 1, "tokens_out": 1})


def test_report_tolerates_rows_without_extra_flags():  # Review Focus 4: M1 rows
    md = render(ROWS, {}, META)
    assert "Extra flags" in md and "Pass 95% CI" in md


def test_extra_flags_column_counts_rows():
    rows = [dict(row("lean", "t1", True, 250), extra_flags=["location"]), row("raw", "t1", True, 1000)]
    assert "| lean | 1/1 |" in render(rows, {}, META)


def test_break_even_zero_extraction_tokens_is_not_measured():
    assert "not measured" in break_even(ROWS, {"extracted": 10, "seconds": 400.0, "tokens_in": 0, "tokens_out": 0})
