import json

from josc.server import MAX_TOOL_RESULT_CHARS, _finalize_payload, _tool_list


def _paper(i: int, abstract_chars: int = 20) -> dict:
    return {
        "doi": f"10.1/{i}",
        "title": f"Paper {i}",
        "abstract": "a" * abstract_chars,
        "year": 2024,
        "authors": ["A"],
        "venue": "V",
        "citation_count": i,
        "topic_paths": [["Physical Sciences", "Computer Science", "AI"]],
        "keywords": ["k1", "k2", "k3"],
        "sources": ["openalex"],
        "ids": {"openalex": f"https://openalex.org/W{i}"},
    }


def _payload(n: int, abstract_chars: int = 20) -> dict:
    return {
        "results": [_paper(i, abstract_chars) for i in range(n)],
        "errors": {},
        "counts": {"openalex": n},
    }


def test_finalize_projects_requested_fields():
    out = _finalize_payload(
        {"fields": ["title", "year", "doi"]}, _payload(2)
    )

    assert out["results"] == [
        {"title": "Paper 0", "year": 2024, "doi": "10.1/0"},
        {"title": "Paper 1", "year": 2024, "doi": "10.1/1"},
    ]
    assert out["counts"] == {"openalex": 2}


def test_finalize_keeps_unknown_field_as_none():
    out = _finalize_payload({"fields": ["title", "nope"]}, _payload(1))
    assert out["results"][0] == {"title": "Paper 0", "nope": None}


def test_finalize_leaves_small_payload_untouched():
    payload = _payload(2)
    out = _finalize_payload({}, payload)
    assert out == payload
    assert "truncated" not in out


def test_finalize_shrinks_oversized_payload_under_budget():
    payload = _payload(200, abstract_chars=2000)
    assert len(json.dumps(payload)) > MAX_TOOL_RESULT_CHARS

    out = _finalize_payload({}, payload)

    assert len(json.dumps(out, ensure_ascii=False)) <= MAX_TOOL_RESULT_CHARS
    assert out["truncated"] is True
    assert out["total_results"] == 200
    assert out["results"]
    assert "truncation_note" in out


def test_finalize_cuts_results_when_minimal_fields_still_too_large():
    payload = {
        "results": [
            {"title": f"Paper {i}", "doi": f"10.1/{i}"} for i in range(3_000)
        ],
        "counts": {"openalex": 3_000},
    }
    assert len(json.dumps(payload)) > MAX_TOOL_RESULT_CHARS

    out = _finalize_payload({}, payload)

    assert len(json.dumps(out, ensure_ascii=False)) <= MAX_TOOL_RESULT_CHARS
    assert out["truncated"] is True
    assert out["total_results"] == 3_000
    assert 0 < len(out["results"]) < 3_000


def test_finalize_prefers_keeping_all_titles_over_abstracts():
    payload = _payload(80, abstract_chars=3000)
    out = _finalize_payload({}, payload)

    assert len(json.dumps(out, ensure_ascii=False)) <= MAX_TOOL_RESULT_CHARS
    # Titles survive; heavy fields are dropped before results are cut.
    assert out["results"]
    assert all("title" in paper for paper in out["results"])


def test_finalize_does_not_mutate_input():
    payload = _payload(3, abstract_chars=10)
    original = json.dumps(payload, sort_keys=True)
    _finalize_payload({"fields": ["title"]}, payload)
    assert json.dumps(payload, sort_keys=True) == original


def test_search_schemas_advertise_fields():
    schemas = {tool.name: tool.inputSchema for tool in _tool_list()}
    assert "fields" in schemas["search_all"]["properties"]
    assert "fields" in schemas["search_openalex"]["properties"]
