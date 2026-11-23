"""Tests for the model-free provenance and claim-faithfulness audit."""

from __future__ import annotations

import json

import pytest

from paperassist.provenance_audit import (
    audit,
    extract_citation_contexts,
    extract_locators,
    load_locators_payload,
)

EXCERPT = "Alpha study reports that alpha matters because of gamma effects."

REFS = {
    "bundle": {
        "excerpts": [
            {"source_id": "s1.md", "path": "s1.md", "excerpt": EXCERPT}
        ]
    },
    "key_sources": {"k1": "s1.md"},
}


def draft(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_no_citations_passes():
    report = audit("Plain prose without any citation.\n")
    assert report.citations_total == 0
    assert report.passed is True
    assert report.grounded_ratio == 1.0
    assert report.unique_keys == ()


def test_citation_contexts_multi_key():
    text = draft(r"Both ideas \cite{k1, k2} stand.")
    contexts = extract_citation_contexts(text)
    assert [context.key for context in contexts] == ["k1", "k2"]
    assert contexts[0].sentence.startswith("Both ideas")


def test_anchorless_citation_fails():
    text = draft(r"Alpha matters \cite{k1}.")
    report = audit(text, references_payload=REFS)
    assert report.unique_keys == ("k1",)
    assert report.anchorless_keys == ("k1",)
    assert report.passed is False
    assert "no locator" in report.warnings[0]


def test_grounded_locator_passes():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=2, quote="alpha matters because of gamma effects"}',
    )
    locators = extract_locators(text)
    assert [locator.key for locator in locators] == ["k1"]
    assert locators[0].page == "2"
    report = audit(text, locators=locators, references_payload=REFS)
    assert report.passed is True
    assert report.grounded_ratio == 1.0


def test_ungrounded_quote_fails():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=3, quote="a span that is not in the source"}',
    )
    report = audit(text, locators=extract_locators(text), references_payload=REFS)
    assert report.passed is False
    assert report.ungrounded_keys == ("k1",)


def test_quote_grounding_ignores_case_and_whitespace():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=1, quote="ALPHA   MATTERS because of gamma effects"}',
    )
    report = audit(text, locators=extract_locators(text), references_payload=REFS)
    assert report.passed is True
    assert report.grounded_ratio == 1.0


def test_unverified_when_no_excerpt_loaded():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=1, quote="alpha matters because of gamma effects"}',
    )
    report = audit(text, locators=extract_locators(text), references_payload=None)
    assert report.ungrounded_keys == ()
    assert report.unverified_keys == ("k1",)


def test_line_range_locator_parsing():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: lines=40-52, quote="alpha matters because of gamma effects"}',
    )
    locator = extract_locators(text)[0]
    assert locator.line_start == 40
    assert locator.line_end == 52


def test_payload_locators_are_accepted():
    locators = load_locators_payload(
        {"locators": [{"key": "k1", "lines": "40-52", "quote": EXCERPT}]}
    )
    assert len(locators) == 1
    assert locators[0].line_start == 40
    assert locators[0].line_end == 52


def test_require_locators_false_allows_anchorless():
    text = draft(r"Alpha matters \cite{k1}.")
    report = audit(
        text, references_payload=REFS, require_locators=False
    )
    assert report.anchorless_keys == ("k1",)
    assert report.passed is True


def test_min_grounding_ratio_threshold():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=9, quote="not present anywhere in the source"}',
    )
    strict = audit(
        text,
        locators=extract_locators(text),
        references_payload=REFS,
        min_grounding_ratio=0.5,
    )
    assert strict.passed is False


def test_report_is_json_serialisable():
    text = draft(
        r"Alpha matters \cite{k1}.",
        '% @locator{k1: page=2, quote="alpha matters because of gamma effects"}',
    )
    report = audit(text, locators=extract_locators(text), references_payload=REFS)
    encoded = json.dumps(report.to_dict())
    assert "paperassist.provenance-audit/v1" in encoded


@pytest.mark.parametrize("marker", ["page", "lines"])
def test_locator_field_variants(marker):
    value = "page=5" if marker == "page" else "lines=5-8"
    text = draft(
        r"Alpha matters \cite{k1}.",
        f'% @locator{{k1: {value}, quote="alpha matters because of gamma effects"}}',
    )
    locator = extract_locators(text)[0]
    if marker == "page":
        assert locator.page == "5"
    else:
        assert locator.line_start == 5 and locator.line_end == 8
