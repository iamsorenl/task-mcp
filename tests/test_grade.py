from task_mcp.grade import grade, parse_answer

T = {"expected": {"fit": "no", "red_flags": ["hours_996"]}}


def out(final, stopped=None):
    return {"final": final, "stopped": stopped}


def test_parse_answer_finds_json_in_text():
    assert parse_answer('Sure: {"fit": "yes", "red_flags": []} done') == {"fit": "yes", "red_flags": []}


def test_parse_answer_none_when_missing():
    assert parse_answer("I think no") is None


def test_pass_needs_fit_and_all_flags():
    g = grade(T, out('{"fit": "No", "red_flags": [{"type": "hours_996", "quote": "x"}]}'))
    assert g["pass"] and g["label"] == "pass" and g["flag_recall"] == 1.0


def test_missed_flag_fails_even_if_fit_matches():
    g = grade(T, out('{"fit": "no", "red_flags": []}'))
    assert g["label"] == "missed_flag" and not g["pass"] and g["fit_ok"]


def test_wrong_fit():
    assert grade(T, out('{"fit": "yes", "red_flags": [{"type": "hours_996"}]}'))["label"] == "wrong_fit"


def test_bad_json():
    assert grade(T, out("I think no"))["label"] == "bad_json"


def test_stopped_run():
    assert grade(T, out("", stopped="step_limit"))["label"] == "stopped"


def test_no_expected_flags_is_full_recall():
    assert grade({"expected": {"fit": "yes", "red_flags": []}}, out('{"fit": "yes", "red_flags": []}'))["pass"]


def test_flags_as_plain_strings_count():
    assert grade(T, out('{"fit": "no", "red_flags": ["hours_996"]}'))["pass"]


def test_grade_reports_extra_flags_without_failing():
    t = {"expected": {"fit": "no", "red_flags": ["seniority"]}}
    g = grade(t, out('{"fit":"no","red_flags":[{"type":"seniority"},{"type":"location"}]}'))
    assert g["pass"] and g["extra_flags"] == ["location"]


def test_grade_extra_flags_empty_on_bad_json():
    assert grade(T, out("nope"))["extra_flags"] == []
