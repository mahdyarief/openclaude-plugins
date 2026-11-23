from __future__ import annotations

import pytest

from paperassist.claim_ledger import _quantity_units
from paperassist.corpus_binder import parse_bib_entries
from paperassist.provenance_audit import Locator
from paperassist.reporting_checks import (
    LOCATOR_NO_TEXT,
    LOCATOR_NOT_FOUND,
    LOCATOR_VERIFIED,
    ReferencePolicy,
    audit_references,
    check_declarations,
    check_prisma_flow,
    cited_keys,
    detect_paper_type,
    load_retraction_dois,
    resolve_paper_type,
    verify_locator_quotes,
)

FLOW_OK = {
    "_counts": True,
    "identification": {
        "identified_by_database": {"scopus": 600, "wos": 400},
        "records_identified": 1000,
        "duplicates_removed": 200,
    },
    "records_screened": 800,
    "records_excluded": 650,
    "reports_sought": 150,
    "reports_not_retrieved": 10,
    "reports_assessed": 140,
    "reports_excluded": 100,
    "exclusion_reasons": {"wrong population": 60, "no outcome": 40},
    "studies_included": 40,
}


def test_prisma_flow_that_adds_up_passes():
    flow = check_prisma_flow([FLOW_OK])
    assert flow.available and flow.passed
    names = {identity.name for identity in flow.identities}
    assert {"identification", "screening", "retrieval", "eligibility"} <= names
    assert {"identified_breakdown", "excluded_fulltext_breakdown"} <= names


def test_prisma_flow_arithmetic_error_is_reported():
    broken = {**FLOW_OK, "studies_included": 45}
    flow = check_prisma_flow([broken])
    failed = [identity for identity in flow.identities if not identity.passed]
    assert [identity.name for identity in failed] == ["eligibility"]
    assert failed[0].expected == 40 and failed[0].reported == 45


def test_prisma_flow_unreported_stages_are_unchecked_not_guessed():
    flow = check_prisma_flow([{"records_identified": 10, "studies_included": 3}])
    assert flow.identities == ()
    assert set(flow.unchecked) == {"identification", "screening", "retrieval", "eligibility"}


def test_paper_type_detection():
    assert detect_paper_type("We train a model.", study_count=3) == "review"
    assert detect_paper_type("A systematic review following PRISMA.") == "review"
    assert detect_paper_type("Mengikuti PRISMA dengan kriteria inklusi.") == "review"
    assert detect_paper_type("We propose a classifier and evaluate it.") == "empirical"
    assert resolve_paper_type("slr", "x") == "review"
    with pytest.raises(ValueError):
        resolve_paper_type("essay", "x")


DECLARED = r"""
\section{Results} Large language models are discussed throughout this paper.
\section*{Declarations}
\paragraph{Competing interests} The authors declare no competing interests.
\paragraph{Funding} This work received no specific funding.
\paragraph{Data availability} The data are available at Zenodo.
\paragraph{Use of generative AI} The authors used ChatGPT to edit language.
"""


def test_declarations_are_read_from_declaration_headings_only():
    check = check_declarations(DECLARED)
    assert check.missing == ()
    # An AI paper mentioning LLMs in its body has not disclosed its own AI use.
    body_only = check_declarations(r"\section{Method} We fine-tune large language models.")
    assert "ai_use" in body_only.missing


def test_ethics_required_only_with_human_participants():
    survey = check_declarations(r"\section{Method} 120 respondents completed a questionnaire.")
    assert survey.ethics_expected and "ethics" in survey.missing
    approved = check_declarations(
        r"\section{Method} 120 respondents gave informed consent; the ethics committee approved."
    )
    assert "ethics" not in approved.missing


def test_custom_required_declarations():
    check = check_declarations(DECLARED, required=["author_contributions"])
    assert check.missing == ("author_contributions",)
    with pytest.raises(ValueError):
        check_declarations(DECLARED, required=["horoscope"])


BIB = r"""
@article{new1, title={A}, year={2023}, doi={10.1/new1}}
@inproceedings{new2, title={B}, year={2021}}
@book{old1, title={C}, year={1998}}
@misc{web1, title={D}}
@article{retr, title={E}, year={2020}, doi={https://doi.org/10.5555/RETR}}
"""


def test_reference_recency_primary_share_and_retractions():
    retractions = load_retraction_dois(
        "Title,OriginalPaperDOI,RetractionNature\n"
        "E,10.5555/retr,Retraction\n"
        "F,10.9/other,Expression of concern\n"
    )
    audit = audit_references(
        parse_bib_entries(BIB),
        policy=ReferencePolicy(reference_year=2026),
        retractions=retractions,
    )
    assert audit.entries == 5
    assert audit.with_year == 4
    assert audit.recent == 3
    assert audit.primary == 3
    assert audit.retracted == (("retr", "10.5555/retr", "Retraction"),)


def test_reference_audit_uses_cited_entries_only():
    audit = audit_references(parse_bib_entries(BIB), cited_keys=["old1"])
    assert audit.entries == 1 and audit.primary == 0


def test_reference_policy_validation():
    assert ReferencePolicy.from_payload({"recent_years": 5}).recent_years == 5
    with pytest.raises(ValueError):
        ReferencePolicy.from_payload({"recent": 5})
    with pytest.raises(ValueError):
        ReferencePolicy.from_payload({"min_recent_share": 2})


def test_retraction_csv_needs_a_doi_column():
    with pytest.raises(ValueError):
        load_retraction_dois("title\nx\n")
    assert load_retraction_dois("doi\n10.1/x\n") == {"10.1/x": "Retraction"}


def test_locator_quotes_are_verified_against_source_text():
    locators = [
        Locator(key="a", quote="improves recall by twelve points"),
        Locator(key="b", quote="a sentence the paper never wrote"),
        Locator(key="c", quote="anything"),
    ]
    texts = {
        "a": "Results. The method im-\nproves Recall by twelve points on average.",
        "b": "Something else entirely.",
    }
    status = verify_locator_quotes(locators, texts)
    assert status == {"a": LOCATOR_VERIFIED, "b": LOCATOR_NOT_FOUND, "c": LOCATOR_NO_TEXT}


def test_cited_keys_handles_variants_and_order():
    text = r"See \citep[p.~3]{b, a} and \citet{a} and \cite{c}."
    assert cited_keys(text) == ["b", "a", "c"]


def test_percent_word_is_a_percentage_not_a_count():
    # Regression: the pattern held literal backspace characters instead of \b.
    assert _quantity_units("45 persen") == _quantity_units("45%")
    assert _quantity_units("45 persen") != _quantity_units("45 studi")
