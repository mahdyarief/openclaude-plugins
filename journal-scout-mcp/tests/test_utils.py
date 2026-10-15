from journal_scout_mcp.utils import (
    first_of,
    normalize_doi,
    normalize_title,
    parse_int,
    parse_year,
    strip_jats,
)


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


def test_first_of_unwraps_sequences():
    assert first_of(["a", "b"]) == "a"
    assert first_of(("only",)) == "only"
    assert first_of([]) is None


def test_first_of_passes_through_scalars():
    assert first_of("plain") == "plain"
    assert first_of(7) == 7
    assert first_of(None) is None


def test_parse_year_accepts_dates_and_ints():
    assert parse_year("2017-06-12") == 2017
    assert parse_year("2017") == 2017
    assert parse_year(1997) == 1997


def test_parse_year_rejects_noise():
    assert parse_year(None) is None
    assert parse_year("not a year") is None
    assert parse_year(True) is None


def test_parse_int_does_not_truncate_short_counters():
    # A citation count like "42" must survive intact (unlike parse_year).
    assert parse_int("42") == 42
    assert parse_int(42000) == 42000
    assert parse_int("0") == 0


def test_parse_int_rejects_non_numeric():
    assert parse_int(None) is None
    assert parse_int("") is None
    assert parse_int("many") is None
