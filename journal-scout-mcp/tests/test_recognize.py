from josc.recognize import find_doi


def test_find_doi_reads_a_plain_doi():
    assert find_doi("Available at https://doi.org/10.1109/5.771073 today") == "10.1109/5.771073"


def test_find_doi_reads_a_bare_doi():
    assert find_doi("DOI: 10.1038/nature14539") == "10.1038/nature14539"


def test_find_doi_ignores_trailing_punctuation():
    assert find_doi("See 10.1016/j.jbi.2020.103433.") == "10.1016/j.jbi.2020.103433"


def test_find_doi_returns_none_when_absent():
    assert find_doi("No identifier on this page") is None
