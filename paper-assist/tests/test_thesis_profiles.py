from __future__ import annotations

import pytest

from paperassist.thesis_profiles import (
    THESIS_PROFILE_SCHEMA,
    detect_thesis_profiles,
    format_thesis_profile_report,
    list_thesis_profiles,
    lookup_thesis_profiles,
    thesis_preamble,
    thesis_profile,
)


def test_list_thesis_profiles_and_scopes():
    all_profiles = list_thesis_profiles()
    assert len(all_profiles) >= 3
    assert {p["profile_id"] for p in all_profiles} >= {
        "id-telkom-tesis",
        "id-thesis-generic",
        "intl-thesis-generic",
    }
    indo = list_thesis_profiles("indonesia")
    assert indo and all(p["scope"] == "indonesia" for p in indo)


def test_lookup_requires_query():
    with pytest.raises(ValueError):
        lookup_thesis_profiles("")


def test_lookup_exact_alias_telkom():
    r = lookup_thesis_profiles("telkom")
    assert r["schema"] == THESIS_PROFILE_SCHEMA
    assert r["exact"] is True
    assert r["matches"][0]["profile_id"] == "id-telkom-tesis"


def test_lookup_skripsi_matches_indonesian_baseline():
    ids = [m["profile_id"] for m in lookup_thesis_profiles("skripsi")["matches"]]
    assert "id-thesis-generic" in ids


def test_telkom_profile_margins_and_spacing():
    p = thesis_profile("id-telkom-tesis")
    assert p.body_font == "Times New Roman"
    assert p.body_font_size_pt == 12
    assert p.line_spacing == 1.5
    assert p.margins_cm == {"left": 4.0, "top": 3.0, "right": 2.5, "bottom": 2.5}
    assert p.paper_size == "A4"


def test_profiles_declare_sources():
    assert all(p["sources"] for p in list_thesis_profiles())


def test_preamble_is_usable_latex():
    pre = thesis_preamble("id-telkom-tesis")
    assert pre.startswith(r"\documentclass[12pt,a4paper]{report}")
    assert r"\setmainfont{Times New Roman}" in pre
    assert "left=4cm" in pre and "top=3cm" in pre
    assert r"\onehalfspacing" in pre
    assert thesis_preamble() == thesis_preamble("id-thesis-generic")


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        thesis_profile("nope")


def test_detect_generic_report_does_not_pick_campus_profile():
    d = detect_thesis_profiles(
        r"\documentclass[12pt,a4paper]{report}" + "\n" + r"\begin{document}x\end{document}"
    )
    assert d["documentclass"] == "report"
    assert d["matches"]
    assert d["matches"][0]["profile_id"] != "id-telkom-tesis"


def test_detect_telkom_token_ranks_campus_profile_first():
    src = (
        r"\documentclass[12pt,a4paper]{report}"
        + "\n"
        + r"\title{Tesis Magister Universitas Telkom}"
        + "\n"
        + r"\begin{document}Universitas Telkom\end{document}"
    )
    d = detect_thesis_profiles(src)
    assert d["matches"][0]["profile_id"] == "id-telkom-tesis"
    assert any("telkom" in r for r in d["matches"][0]["reasons"])


def test_report_includes_preamble_and_numbers():
    md = format_thesis_profile_report(lookup_thesis_profiles("telkom"))
    assert "Times New Roman 12 pt" in md
    assert "4/3/2.5/2.5 cm" in md
    assert r"\documentclass" in md
    assert "sources:" in md
