from __future__ import annotations

from paperassist.writing_pack import _thesis_profile


def test_thesis_profile_default_is_campus_agnostic():
    p = _thesis_profile({})
    assert p["documentclass"] == "report"
    assert p["profile_id"] is None
    assert "font" not in p
    assert p["front_matter"]["titlepage"] is True


def test_thesis_profile_seeds_from_telkom_preset():
    p = _thesis_profile({"thesis_profile": {"profile_id": "id-telkom-tesis"}})
    assert p["profile_id"] == "id-telkom-tesis"
    assert p["font"] == "Times New Roman"
    assert p["font_size_pt"] == 12
    assert p["line_spacing"] == 1.5
    assert p["margins_cm"] == {"left": 4.0, "top": 3.0, "right": 2.5, "bottom": 2.5}
    assert p["paper_size"] == "A4"
    assert "left=4cm" in p["latex_preamble"]
    assert p["sources"]


def test_explicit_payload_overrides_preset():
    p = _thesis_profile(
        {
            "thesis_profile": {
                "profile_id": "id-telkom-tesis",
                "line_spacing": 2.0,
                "margins_cm": {"left": 3.0, "top": 2.5, "right": 2.5, "bottom": 2.5},
            }
        }
    )
    assert p["line_spacing"] == 2.0
    assert p["margins_cm"]["left"] == 3.0
    assert p["font"] == "Times New Roman"  # still inherited from the preset
