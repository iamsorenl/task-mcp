from task_mcp.fields import apply_fields, est_tokens, field_paths, get_path, html_to_text

JOB = {"id": 1, "title": "FDE", "location": {"name": "SF"}, "content": "&lt;p&gt;Hi&lt;/p&gt;",
       "offices": [{"id": 9, "name": "SF"}, {"id": 8, "name": "NYC", "x": 1}]}


def test_field_paths():
    assert set(field_paths(JOB)) == {"id", "title", "location.name", "content",
                                     "offices[*].id", "offices[*].name", "offices[*].x"}


def test_get_path_array_and_missing():
    assert get_path(JOB, "offices[*].name") == ["SF", "NYC"]
    assert get_path(JOB, "nope.x") is None


def test_apply_fields_keeps_nested_and_drops_rest():
    assert apply_fields(JOB, {"title": "keep", "location.name": "keep"}) == {"title": "FDE", "location": {"name": "SF"}}


def test_apply_fields_array_paths():
    assert apply_fields(JOB, {"offices[*].name": "keep"}) == {"offices": [{"name": "SF"}, {"name": "NYC"}]}


def test_apply_fields_extract_hook():
    out = apply_fields(JOB, {"content": {"extract": "d"}}, extract_fn=lambda name, v: {"n": name, "v": v})
    assert out == {"content": {"n": "d", "v": "&lt;p&gt;Hi&lt;/p&gt;"}}


def test_html_to_text_double_escaped():
    assert html_to_text("&lt;p&gt;A &amp;amp; B&lt;/p&gt;&lt;p&gt;C&lt;/p&gt;") == "A & B\nC"


def test_est_tokens_labels_chars_over_four():
    assert est_tokens("x" * 40) == 10 and est_tokens({"a": 1}) == len('{"a": 1}') // 4
