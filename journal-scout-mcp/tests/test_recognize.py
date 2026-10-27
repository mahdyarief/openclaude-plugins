import builtins
import pytest

from josc.models import Paper
from josc.recognize import find_doi, guess_title, recognize_document
from josc.pdf_text import extract_pdf_text


def test_find_doi_reads_a_plain_doi():
    assert find_doi("Available at https://doi.org/10.1109/5.771073 today") == "10.1109/5.771073"


def test_find_doi_reads_a_bare_doi():
    assert find_doi("DOI: 10.1038/nature14539") == "10.1038/nature14539"


def test_find_doi_ignores_trailing_punctuation():
    assert find_doi("See 10.1016/j.jbi.2020.103433.") == "10.1016/j.jbi.2020.103433"


def test_find_doi_returns_none_when_absent():
    assert find_doi("No identifier on this page") is None


def test_guess_title_picks_the_longest_early_line():
    text = "Neural Computation\nLong Short-Term Memory\nSepp Hochreiter\n1997\n"
    assert guess_title(text) == "Long Short-Term Memory"


def test_guess_title_returns_none_for_blank_text():
    assert guess_title("   \n\n  ") is None


async def test_recognize_document_prefers_doi():
    seen = []

    async def resolver(identifier):
        seen.append(identifier)
        return Paper(doi=identifier, title="Resolved")

    paper = await recognize_document("doi 10.1/abc", resolver)
    assert paper is not None
    assert paper.title == "Resolved"
    assert seen == ["10.1/abc"]


async def test_recognize_document_falls_back_to_title():
    seen = []

    async def resolver(identifier):
        seen.append(identifier)
        return None

    await recognize_document("Attention Is All You Need\n2017\n", resolver)
    assert seen == ["Attention Is All You Need"]


async def test_recognize_document_returns_none_without_identifier():
    async def resolver(identifier):
        raise AssertionError("resolver must not be called")

    assert await recognize_document("", resolver) is None


def test_extract_pdf_text_explains_a_missing_dependency(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("no pypdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    with pytest.raises(RuntimeError) as excinfo:
        extract_pdf_text("whatever.pdf")
    assert "journal-scout-mcp[pdf]" in str(excinfo.value)
