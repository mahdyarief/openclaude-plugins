from journal_scout_mcp.utils import normalize_doi, normalize_title, strip_jats


def test_normalize_doi_strips_prefixes():
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("doi:10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_empty_is_none():
    assert normalize_doi("") is None
    assert normalize_doi(None) is None


def test_normalize_title_drops_punctuation():
    assert normalize_title("Attention Is All You Need!") == "attention is all you need"
    assert normalize_title("Deep   Learning: A Survey") == "deep learning a survey"


def test_strip_jats():
    assert strip_jats("<jats:p>Hello &amp; bye</jats:p>") == "Hello & bye"
    assert strip_jats(None) is None
