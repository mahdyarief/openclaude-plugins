from josc.merge import merge_two
from josc.models import Paper
from josc.providers.crossref import build_retraction
from josc.retractions import (
    RETRACTION_REASON_KEYS,
    RetractionInfo,
    normalize_reason,
)


def test_taxonomy_matches_zotero_key_count():
    assert len(RETRACTION_REASON_KEYS) == 111


def test_taxonomy_contains_known_zotero_keys():
    assert "Duplication of/in Image" in RETRACTION_REASON_KEYS
    assert "Falsification/Fabrication of Data" in RETRACTION_REASON_KEYS
    assert "Paper Mill" in RETRACTION_REASON_KEYS


def test_normalize_reason_is_case_insensitive():
    assert normalize_reason("paper mill") == "Paper Mill"


def test_normalize_reason_returns_none_for_unknown_values():
    assert normalize_reason("Something Zotero Never Defined") is None
    assert normalize_reason(None) is None


def test_retraction_info_to_dict_is_json_safe():
    info = RetractionInfo(
        reasons=["Paper Mill"],
        notice_doi="10.1/notice",
        notice_url="https://example.test/notice",
        notice_date="2024-03-01",
        source="crossref",
    )
    assert info.to_dict() == {
        "reasons": ["Paper Mill"],
        "notice_doi": "10.1/notice",
        "notice_url": "https://example.test/notice",
        "notice_date": "2024-03-01",
        "source": "crossref",
    }


def test_paper_defaults_to_no_retraction_payload():
    paper = Paper(title="A Paper")
    assert paper.retraction is None
    assert paper.to_dict()["retraction"] is None


def test_paper_serializes_retraction_payload():
    paper = Paper(
        title="A Paper",
        is_retracted=True,
        retraction=RetractionInfo(reasons=["Paper Mill"], source="crossref"),
    )
    assert paper.to_dict()["retraction"] == {
        "reasons": ["Paper Mill"],
        "notice_doi": None,
        "notice_url": None,
        "notice_date": None,
        "source": "crossref",
    }


def test_build_retraction_returns_none_without_update_to():
    assert build_retraction({"DOI": "10.1/a"}) is None


def test_build_retraction_reads_retraction_notice():
    item = {
        "DOI": "10.1/a",
        "update-to": [
            {
                "type": "retraction",
                "DOI": "10.1/notice",
                "updated": {"date-parts": [[2024, 3, 1]]},
                "label": "Retraction",
                "URL": "https://example.test/notice",
            }
        ],
    }
    info = build_retraction(item)
    assert info is not None
    assert info.notice_doi == "10.1/notice"
    assert info.notice_url == "https://example.test/notice"
    assert info.notice_date == "2024-03-01"
    assert info.source == "crossref"
    assert info.reasons == ["Updated to Retraction"]


def test_build_retraction_ignores_correction_updates():
    item = {"update-to": [{"type": "correction", "DOI": "10.1/fix"}]}
    assert build_retraction(item) is None


def test_build_retraction_ignores_unknown_reason_labels():
    item = {"update-to": [{"type": "retraction", "DOI": "10.1/n", "label": "Mystery"}]}
    info = build_retraction(item)
    assert info is not None
    assert info.reasons == []


def test_crossref_provider_attaches_retraction_payload():
    from josc.providers.crossref import CrossrefProvider

    provider = CrossrefProvider(None)
    paper = provider._to_paper(
        {
            "DOI": "10.1/a",
            "title": ["A Paper"],
            "update-to": [{"type": "retraction", "DOI": "10.1/n", "label": "Retraction"}],
        }
    )
    assert paper.retraction is not None
    assert paper.retraction.notice_doi == "10.1/n"


def test_merge_two_keeps_the_richest_retraction_payload():
    thin = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(reasons=["Updated to Retraction"], source="crossref"),
    )
    rich = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(
            reasons=["Paper Mill", "Falsification/Fabrication of Data"],
            notice_doi="10.1/n",
            source="crossref",
        ),
    )
    merged = merge_two(thin, rich)
    assert merged.retraction is not None
    assert merged.retraction.notice_doi == "10.1/n"
    assert len(merged.retraction.reasons) == 2


def test_merge_two_syncs_is_retracted_from_payload():
    plain = Paper(doi="10.1/a", title="P")
    flagged = Paper(
        doi="10.1/a",
        title="P",
        retraction=RetractionInfo(reasons=["Paper Mill"], source="crossref"),
    )
    merged = merge_two(plain, flagged)
    assert merged.is_retracted is True
