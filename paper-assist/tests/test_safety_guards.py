from __future__ import annotations

import pytest

from paperassist.anti_ai_style import (
    detect_formulaic_phrases,
    is_uniform_rhythm,
    sentence_length_cv,
)
from paperassist.journal_profiles import list_profiles
from paperassist.latex_safety import FORBIDDEN_LATEX
from paperassist.protected_blocks import (
    PROTECTED_END,
    PROTECTED_START,
    ProtectedBlockViolation,
    ProtectedEditTransaction,
    extract_protected_blocks,
    protected_blocks_sha256,
)

BLOCK = f"{PROTECTED_START}\nAccuracy 91.2.\n{PROTECTED_END}"


def test_extract_and_hash_protected_blocks():
    text = f"before\n{BLOCK}\nafter"
    assert extract_protected_blocks(text) == (BLOCK,)
    assert protected_blocks_sha256(text) == protected_blocks_sha256(f"changed\n{BLOCK}\n")


@pytest.mark.parametrize(
    "text",
    [
        f"{PROTECTED_START}\n{PROTECTED_START}\n{PROTECTED_END}",
        f"{PROTECTED_END}\n{PROTECTED_START}",
        f"{PROTECTED_START}\nno end",
    ],
)
def test_malformed_markers_fail_closed(text):
    with pytest.raises(ProtectedBlockViolation):
        extract_protected_blocks(text)


def test_transaction_rolls_back_protected_edit(tmp_path):
    path = tmp_path / "main.tex"
    original = f"intro\n{BLOCK}\n"
    path.write_text(original, encoding="utf-8")
    transaction = ProtectedEditTransaction(path)
    path.write_text(original.replace("91.2", "99.9"), encoding="utf-8")
    with pytest.raises(ProtectedBlockViolation):
        transaction.verify()
    assert path.read_text(encoding="utf-8") == original


def test_transaction_accepts_edits_outside_blocks(tmp_path):
    path = tmp_path / "main.tex"
    path.write_text(f"intro\n{BLOCK}\n", encoding="utf-8")
    transaction = ProtectedEditTransaction(path)
    path.write_text(f"new intro\n{BLOCK}\n", encoding="utf-8")
    assert transaction.verify() == protected_blocks_sha256(BLOCK)


@pytest.mark.parametrize(
    "source",
    [
        r"\input{secret}",
        r"\immediate\write18{rm -rf /}",
        r"\def\x{y}",
        r"\begin{filecontents}{a.tex}",
        r"\usepackage{shellesc}",
        r"\makeatletter",
    ],
)
def test_forbidden_latex_is_detected(source):
    assert FORBIDDEN_LATEX.search(source)


@pytest.mark.parametrize(
    "source",
    [r"\section{Method}", r"\cite{key}", r"\textbf{bold}", r"\begin{table}\end{table}"],
)
def test_ordinary_latex_is_allowed(source):
    assert FORBIDDEN_LATEX.search(source) is None


def test_formulaic_phrases_are_flagged_but_academic_terms_are_not():
    hits = detect_formulaic_phrases(
        "Di era digital, tidak dapat dipungkiri bahwa data memainkan peran penting."
    )
    assert {hit.category for hit in hits} == {"generic opener", "filler", "generic claim"}
    assert detect_formulaic_phrases("Hasil ini signifikan menurut literatur.") == []


def test_rhythm_needs_enough_sentences():
    uniform = " ".join(["Model ini dilatih pada data uji."] * 6)
    assert is_uniform_rhythm(uniform)
    assert sentence_length_cv("Kalimat pendek. Kalimat kedua.") == 1.0


def test_journal_template_formats_are_tuples_of_formats():
    for profile in list_profiles(None):
        formats = profile["template_formats"]
        assert all(len(item) > 1 for item in formats), profile["profile_id"]
