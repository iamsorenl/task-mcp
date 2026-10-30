import json

import pytest

from task_mcp.extract import Extractor, normalize
from task_mcp.plan import load_plan
from task_mcp.runtime import precompute
from task_mcp.sources import ReplayBackend, record
from tests.helpers import gh_backend, gh_sources

PLAN = load_plan("examples/greenhouse/plan.yaml")
HTML = "&lt;p&gt;You&amp;rsquo;ll own billing &amp;mdash; 5+ years required. We work 6 days a week.&lt;/p&gt;"
GOOD = json.dumps({"scope": "Own billing", "day_to_day": ["billing"],
                   "experience": [{"text": "5+ years", "quote": "5+ years required"}],
                   "red_flags": [{"type": "hours_996", "quote": "We work 6 days a week"}],
                   "pay_range": None, "onsite": None})


def fake(calls, *replies):
    replies = list(replies)

    def complete(prompt):
        calls.append(prompt)
        return replies[min(len(calls), len(replies)) - 1]
    return complete


def test_normalize_maps_curly_quotes_dashes_entities():
    assert normalize("You&rsquo;ll  Own — X") == "you'll own - x"


def test_extract_verifies_quotes_and_keeps_good_ones(tmp_path):
    out = Extractor(PLAN, fake([], GOOD), tmp_path).extract("description_facts", "1", HTML)
    assert out["red_flags"] == [{"type": "hours_996", "quote": "We work 6 days a week"}]
    assert out["unverified"] == []


def test_cache_hit_skips_model(tmp_path):
    calls = []
    ex = Extractor(PLAN, fake(calls, GOOD), tmp_path)
    ex.extract("description_facts", "1", HTML)
    ex.extract("description_facts", "1", HTML)
    assert len(calls) == 1


def test_changed_text_reextracts(tmp_path):
    calls = []
    ex = Extractor(PLAN, fake(calls, GOOD), tmp_path)
    ex.extract("description_facts", "1", HTML)
    ex.extract("description_facts", "1", HTML + "&lt;p&gt;new&lt;/p&gt;")
    assert len(calls) == 2


def test_invented_quote_goes_to_unverified(tmp_path):  # Review Focus 2
    bad = json.dumps({"red_flags": [{"type": "hours_996", "quote": "we work 996"}]})
    out = Extractor(PLAN, fake([], bad), tmp_path).extract("description_facts", "1", HTML)
    assert out["red_flags"] == [] and out["unverified"][0]["quote"] == "we work 996"


def test_curly_quotes_and_entities_still_verify(tmp_path):
    rep = json.dumps({"experience": [{"text": "x", "quote": "You'll own billing - 5+ years"}]})
    out = Extractor(PLAN, fake([], rep), tmp_path).extract("description_facts", "1", HTML)
    assert len(out["experience"]) == 1


def test_unknown_flag_type_becomes_other(tmp_path):
    rep = json.dumps({"red_flags": [{"type": "vibes", "quote": "We work 6 days a week"}]})
    out = Extractor(PLAN, fake([], rep), tmp_path).extract("description_facts", "1", HTML)
    assert out["red_flags"][0]["type"] == "other"


def test_missing_fields_are_null_or_empty(tmp_path):
    out = Extractor(PLAN, fake([], "{}"), tmp_path).extract("description_facts", "1", HTML)
    assert out["pay_range"] is None and out["red_flags"] == [] and out["day_to_day"] == []


def test_empty_text_skips_model(tmp_path):  # Review Focus 2
    calls = []
    out = Extractor(PLAN, fake(calls, GOOD), tmp_path).extract("description_facts", "1", "")
    assert calls == [] and out["pay_range"] is None and out["red_flags"] == []


def test_bad_json_retries_then_fails(tmp_path):  # Review Focus 3
    calls = []
    out = Extractor(PLAN, fake(calls, "not json", "still not"), tmp_path).extract("description_facts", "1", HTML)
    assert len(calls) == 2 and out == {"extract_failed": True}
    assert "not json" in calls[1] or "error" in calls[1].lower()


def test_bad_json_then_good_succeeds(tmp_path):
    calls = []
    out = Extractor(PLAN, fake(calls, "nope", "```json\n" + GOOD + "\n```"), tmp_path).extract("description_facts", "1", HTML)
    assert len(calls) == 2 and out["scope"] == "Own billing"


def test_precompute_counts(tmp_path):
    src = gh_sources()
    record(src, gh_backend(), tmp_path / "rec")
    stats = precompute(PLAN, src, ReplayBackend(tmp_path / "rec"), Extractor(PLAN, fake([], GOOD), tmp_path / "c"))
    assert stats["items"] == 2 and stats["items"] == stats["cached"] + stats["extracted"] + stats["failed"]
    again = precompute(PLAN, src, ReplayBackend(tmp_path / "rec"), Extractor(PLAN, fake([], GOOD), tmp_path / "c"))
    assert again["cached"] == 2


def test_hostile_item_id_stays_inside_cache_dir(tmp_path):
    cache = tmp_path / "cache"
    Extractor(PLAN, fake([], GOOD), cache).extract("description_facts", "../../escaped", HTML)
    assert not list(tmp_path.glob("escaped*")) and not list((tmp_path / "cache").parent.parent.glob("escaped*"))
    assert len(list(cache.rglob("*.json"))) == 1


def test_failure_is_cached(tmp_path):  # otherwise every call to a bad posting costs two model calls
    calls = []
    ex = Extractor(PLAN, fake(calls, "not json"), tmp_path)
    ex.extract("description_facts", "1", HTML)
    out = ex.extract("description_facts", "1", HTML)
    assert len(calls) == 2 and out == {"extract_failed": True} and ex.last == "failed"
