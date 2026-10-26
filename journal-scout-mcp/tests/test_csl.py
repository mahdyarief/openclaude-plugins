from josc.csl import CSL_STYLES, CSLStyleError, paper_to_csl, render_csl


def test_paper_to_csl_maps_core_fields():
    item = paper_to_csl(
        {
            "doi": "10.1/a",
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "venue": "NeurIPS",
            "url": "https://example.test/a",
        }
    )
    assert item["type"] == "article-journal"
    assert item["id"] == "10.1/a"
    assert item["title"] == "Attention Is All You Need"
    assert item["container-title"] == "NeurIPS"
    assert item["DOI"] == "10.1/a"
    assert item["URL"] == "https://example.test/a"
    assert item["issued"] == {"date-parts": [[2017]]}
    assert item["author"] == [
        {"family": "Vaswani", "given": "Ashish"},
        {"family": "Shazeer", "given": "Noam"},
    ]


def test_paper_to_csl_falls_back_to_title_when_doi_missing():
    item = paper_to_csl({"title": "No DOI Here"})
    assert item["id"] == "no doi here"
    assert "DOI" not in item


def test_paper_to_csl_omits_issued_when_year_missing():
    item = paper_to_csl({"title": "Undated"})
    assert "issued" not in item


def test_paper_to_csl_handles_single_token_author():
    item = paper_to_csl({"title": "X", "authors": ["Plato"]})
    assert item["author"] == [{"family": "Plato", "given": ""}]


SAMPLE = [
    {
        "doi": "10.1/a",
        "title": "Attention Is All You Need",
        "year": 2017,
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "venue": "NeurIPS",
    }
]


def test_builtin_styles_are_declared():
    assert set(CSL_STYLES) == {"apa", "vancouver", "chicago"}


def test_render_apa_uses_family_and_initials():
    out = render_csl(SAMPLE, "apa")
    assert out.startswith("Vaswani, A., Shazeer, N. (2017).")
    assert "Attention Is All You Need." in out
    assert "NeurIPS." in out
    assert out.endswith("\n")


def test_render_vancouver_uses_family_and_initials_without_period():
    out = render_csl(SAMPLE, "vancouver")
    assert out.startswith("Vaswani A, Shazeer N. (2017).")
    assert "Attention Is All You Need." in out


def test_render_chicago_quotes_the_title():
    out = render_csl(SAMPLE, "chicago")
    assert '"Attention Is All You Need."' in out
    assert "NeurIPS (2017)." in out


def test_render_empty_input_returns_empty_string():
    assert render_csl([], "apa") == ""


def test_render_accepts_a_custom_style_dict():
    style = {
        "author_format": "family",
        "author_join": "comma",
        "author_limit": 1,
        "title_quotes": False,
        "title_suffix": "",
        "venue_wrap": "",
        "year_wrap": "",
        "include_doi": False,
    }
    out = render_csl(SAMPLE, style)
    assert out.startswith("Vaswani (2017)")
    assert "NeurIPS" in out


def test_render_rejects_a_style_missing_required_keys():
    try:
        render_csl(SAMPLE, {"author_format": "family"})
    except CSLStyleError as exc:
        assert "missing" in str(exc).lower()
    else:
        raise AssertionError("CSLStyleError was not raised")
