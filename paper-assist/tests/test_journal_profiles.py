from __future__ import annotations

import pytest

from paperassist.journal_profiles import (
    PROFILE_SCHEMA,
    detect_profiles,
    format_profile_report,
    list_profiles,
    lookup_profiles,
)


def test_list_profiles_all_and_scoped():
    all_profiles = list_profiles()
    assert len(all_profiles) >= 6
    assert {p["profile_id"] for p in all_profiles} >= {
        "latex-article-default",
        "id-sinta-generic",
        "intl-elsevier-elsarticle",
        "intl-ieee-ieeetran",
        "intl-springer-nature-snjnl",
        "intl-acm-acmart",
    }
    indo = list_profiles("indonesia")
    assert indo and all(p["scope"] == "indonesia" for p in indo)


def test_lookup_requires_query():
    with pytest.raises(ValueError):
        lookup_profiles("")


def test_lookup_exact_alias():
    r = lookup_profiles("jtim")
    assert r["schema"] == PROFILE_SCHEMA
    assert r["exact"] is True
    assert r["matches"][0]["profile_id"] == "id-jtim-sekawan"


def test_lookup_elsarticle():
    r = lookup_profiles("elsarticle")
    ids = [m["profile_id"] for m in r["matches"]]
    assert "intl-elsevier-elsarticle" in ids


def test_lookup_reports_abstract_layout_and_sources():
    r = lookup_profiles("sinta")
    top = r["matches"][0]
    assert top["abstract_layout"]
    assert top["sources"]


def test_detect_article_default():
    src = r"\documentclass[11pt,a4paper]{article}" + "\n" + r"\begin{document}x\end{document}"
    d = detect_profiles(src)
    assert d["documentclass"] == "article"
    assert d["matches"], "expected at least the stock article profile"
    assert d["matches"][0]["profile_id"] == "latex-article-default"


def test_detect_elsarticle_ranks_first():
    d = detect_profiles(r"\documentclass[preprint,12pt]{elsarticle}")
    assert d["documentclass"] == "elsarticle"
    assert d["matches"][0]["profile_id"] == "intl-elsevier-elsarticle"
    assert d["matches"][0]["score"] > d["matches"][-1]["score"]


def test_detect_ieeetran():
    d = detect_profiles(r"\documentclass[journal]{IEEEtran}")
    assert d["matches"][0]["profile_id"] == "intl-ieee-ieeetran"


def test_format_report_variants():
    assert "lookup" in format_profile_report(lookup_profiles("ieee")).lower()
    listing = {"schema": PROFILE_SCHEMA, "profiles": list_profiles()}
    assert "count=7" in format_profile_report(listing) or "count=" in format_profile_report(listing)
    detection = detect_profiles(r"\documentclass{acmart}")
    assert "detection" in format_profile_report(detection).lower()
