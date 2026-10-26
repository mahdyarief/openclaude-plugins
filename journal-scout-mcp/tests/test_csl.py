from josc.csl import paper_to_csl


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
