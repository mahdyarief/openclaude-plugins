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
