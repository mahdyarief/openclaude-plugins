"""Tests for the two-channel claim ledger."""

from __future__ import annotations

import json

import pytest

from paperassist.claim_ledger import (
    CHANNEL_EVIDENCE,
    CHANNEL_NARRATIVE,
    STATUS_ATTRIBUTED,
    STATUS_DERIVED,
    STATUS_GROUNDED,
    STATUS_NARRATIVE,
    STATUS_UNSUPPORTED,
    LedgerError,
    build_ledger,
    format_ledger_report,
    ledger_from_payload,
)
from paperassist.provenance_audit import Locator

DOC = r"""\documentclass{article}
\usepackage[margin=2.5cm]{geometry}
\begin{document}
\maketitle
\section{Introduction}
Prior work established the baseline \citep{alpha2020}.% @locator{alpha2020: page=3, quote="the baseline improved"}
This sentence merely connects the argument.
We processed 42 claims from 7 sources.
\section{Results}
Accuracy reached 91.5\% on the evaluation set.
\section{Conclusions}
Both ideas converge on the same mechanism.
\end{document}
"""


def test_claims_are_split_into_both_channels():
    ledger = build_ledger(DOC)
    channels = {claim.channel for claim in ledger.claims}
    assert channels == {CHANNEL_EVIDENCE, CHANNEL_NARRATIVE}
    summary = ledger.summary()
    assert summary["evidence_channel"] > 0
    assert summary["narrative_channel"] > 0
    assert summary["evidence_channel"] + summary["narrative_channel"] == summary["claims"]


def test_preamble_is_not_a_claim():
    ledger = build_ledger(DOC)
    assert all(claim.line_start >= 4 for claim in ledger.claims)
    assert not any("margin" in claim.sentence for claim in ledger.claims)


def test_structural_commands_are_not_sentences():
    ledger = build_ledger(DOC)
    assert not any("maketitle" in claim.sentence for claim in ledger.claims)
    assert not any(claim.sentence.strip() == "begin{document}" for claim in ledger.claims)


def test_locator_grounds_the_sentence_it_follows():
    locators = [Locator(key="alpha2020", page="3", quote="the baseline improved")]
    ledger = build_ledger(DOC, locators=locators)
    grounded = [c for c in ledger.claims if c.status == STATUS_GROUNDED]
    assert len(grounded) == 1
    assert "Prior work established" in grounded[0].sentence
    assert grounded[0].locator_keys == ("alpha2020",)
    assert grounded[0].evidence_refs[0]["relation"] == "wasDerivedFrom"


def test_citation_without_excerpt_is_attributed():
    without_locator = DOC.replace(
        '.% @locator{alpha2020: page=3, quote="the baseline improved"}', "."
    )
    ledger = build_ledger(without_locator)
    attributed = [c for c in ledger.claims if c.status == STATUS_ATTRIBUTED]
    assert attributed
    assert attributed[0].citation_keys == ("alpha2020",)


def test_locators_are_extracted_when_none_are_passed():
    ledger = build_ledger(DOC)
    grounded = [c for c in ledger.claims if c.status == STATUS_GROUNDED]
    assert len(grounded) == 1
    assert grounded[0].locator_keys == ("alpha2020",)


def test_explicit_empty_locators_are_respected():
    ledger = build_ledger(DOC, locators=[])
    assert not [c for c in ledger.claims if c.status == STATUS_GROUNDED]


def test_number_matching_a_data_record_is_derived():
    records = [{"id": "s1", "claims": 42, "sources": 7}]
    ledger = build_ledger(DOC, records=records)
    derived = [c for c in ledger.claims if c.status == STATUS_DERIVED]
    assert derived
    joined = " ".join(claim.sentence for claim in derived)
    assert "42" in joined


def test_unmatched_number_is_unsupported():
    ledger = build_ledger(DOC)
    unsupported = ledger.unsupported()
    assert unsupported
    assert any("91.5" in claim.sentence or "91,5" in claim.sentence for claim in unsupported)


def test_universal_claim_without_support_is_unsupported():
    text = r"""\begin{document}
\section{Introduction}
No study reported this quantity.
\end{document}
"""
    ledger = build_ledger(text)
    assert ledger.unsupported()


def test_universal_scope_needs_a_corpus_noun():
    # "every decision" scopes an argument; "every study" claims something about
    # the literature. Only the second is a statement evidence can settle.
    scoped = r"""\begin{document}
\section{Discussion}
Every decision in the adjudication path leaves a trace, so the argument holds.
\end{document}
"""
    assert not build_ledger(scoped).unsupported()

    corpus = r"""\begin{document}
\section{Discussion}
Every study in this review reports a different metric.
\end{document}
"""
    assert build_ledger(corpus).unsupported()


def test_caveat_denies_rather_than_asserts():
    # A sentence that refuses to generalise must not be read as generalising.
    text = r"""\begin{document}
\section{Discussion}
The extraction is not evidence that all studies share one protocol.
\end{document}
"""
    assert not build_ledger(text).unsupported()


def test_connectives_are_narrative():
    ledger = build_ledger(DOC)
    narrative = ledger.by_channel(CHANNEL_NARRATIVE)
    assert any("merely connects" in claim.sentence for claim in narrative)
    assert all(claim.status == STATUS_NARRATIVE for claim in narrative)


def test_sentence_offsets_map_to_real_lines():
    locators = [Locator(key="alpha2020", page="3", quote="the baseline improved")]
    ledger = build_ledger(DOC, locators=locators)
    grounded = next(c for c in ledger.claims if c.status == STATUS_GROUNDED)
    # A paragraph may span several source lines, so search the reported line
    # and the two after it rather than a single line.
    source_lines = DOC.splitlines()
    window = "\n".join(source_lines[grounded.line_start - 1 : grounded.line_start + 2])
    assert "Prior work established" in window


def test_ledger_digest_is_stable_and_sensitive():
    first = build_ledger(DOC)
    second = build_ledger(DOC)
    assert first.digest == second.digest
    changed = build_ledger(DOC.replace("42 claims", "43 claims"))
    assert changed.digest != first.digest


def test_jsonl_channels_do_not_overlap():
    ledger = build_ledger(DOC)
    narrative = {
        json.loads(line)["claim_id"] for line in ledger.to_jsonl(CHANNEL_NARRATIVE).splitlines()
    }
    evidence = {
        json.loads(line)["claim_id"] for line in ledger.to_jsonl(CHANNEL_EVIDENCE).splitlines()
    }
    assert narrative
    assert evidence
    assert not (narrative & evidence)


def test_ledger_serialises():
    ledger = build_ledger(DOC)
    json.dumps(ledger.to_dict())
    assert ledger.to_dict()["schema"] == "paperassist.claim-ledger/v1"


def test_ledger_from_payload_uses_locator_keys():
    ledger = ledger_from_payload(
        DOC,
        {"locators": [{"key": "alpha2020", "page": "3", "quote": "the baseline improved"}]},
    )
    assert any(claim.status == STATUS_GROUNDED for claim in ledger.claims)


def test_report_lists_unsupported_claims():
    report = format_ledger_report(build_ledger(DOC))
    assert "Claim ledger" in report
    assert "Unsupported quantitative assertions" in report


def test_non_text_input_is_rejected():
    with pytest.raises(LedgerError):
        build_ledger(None)  # type: ignore[arg-type]


def test_em_dash_is_preserved_in_sentences():
    text = r"""\begin{document}
\section{Results}
A finding --- stated plainly --- appears here.
\end{document}
"""
    ledger = build_ledger(text)
    assert any("---" in claim.sentence for claim in ledger.claims)


CORPUS_DOC = r"""\begin{document}
\section{Results}
From 265 records, 108 studies entered synthesis.
We excluded 87 records at title and abstract screening.
Precision was reported in 75 studies.
The first submission rejection rate was 24\%.
"""
CORPUS_ROWS = [
    {"_source": "extraction", "class": "coding", "total": 11.1},
    {"_source": "extraction", "class": "coding", "total": 10.4},
    {"_source": "extraction", "class": "fraud", "total": 9.3},
]


def status_by_sentence(ledger):
    return {claim.sentence: claim.status for claim in ledger.claims}


def test_aggregate_counts_are_derived_from_records():
    # The row count is the corpus size, 3, and the only counted nouns the
    # records actually name are the fields "class" and "total".
    text = r"""\begin{document}
\section{Results}
Only 3 rows were extracted.
\end{document}
"""
    ledger = build_ledger(text, records=CORPUS_ROWS)
    assert ledger.claims[0].status == STATUS_DERIVED


def test_proportion_requires_derived_proportion_not_a_count():
    ledger = build_ledger(CORPUS_DOC, records=CORPUS_ROWS)
    status = status_by_sentence(ledger)
    # 24 is close to the row count and to several means, but nothing in the
    # data supports a claim of 24%, so the assertion stays unsupported.
    assert (
        status["The first submission rejection rate was 24\\%."]
        == STATUS_UNSUPPORTED
    )


def test_count_document_contributes_counts_and_proportions():
    text = r"""\begin{document}
\section{Results}
We identified 265 records and included 40,8\% of them.
\end{document}
"""
    ledger = build_ledger(
        text,
        records=[
            {
                "_source": "flow",
                "_counts": True,
                "identified_total": 265,
                "included_total": 108,
            }
        ],
    )
    assert ledger.claims[0].status == STATUS_DERIVED


def test_group_mean_is_derived_from_records():
    text = r"""\begin{document}
\section{Results}
Coding studies scored 10,75 on average.
\end{document}
"""
    ledger = build_ledger(text, records=CORPUS_ROWS)
    assert ledger.claims[0].status == STATUS_DERIVED


def test_wrong_mean_is_not_derived():
    text = r"""\begin{document}
\section{Results}
Coding studies scored 11,90 on average.
\end{document}
"""
    ledger = build_ledger(text, records=CORPUS_ROWS)
    assert ledger.claims[0].status == STATUS_UNSUPPORTED


def test_mixed_confirmed_and_unconfirmed_numbers_stay_unsupported():
    text = r"""\begin{document}
\section{Results}
From 265 records we kept 999 studies.
\end{document}
"""
    ledger = build_ledger(text, records=CORPUS_ROWS)
    assert ledger.claims[0].status == STATUS_UNSUPPORTED


def test_negated_scope_is_not_a_universal_claim():
    # Naming a universal scope in order to reject it is not an assertion about
    # the literature, so it must not demand evidence.
    text = r"""\documentclass{article}
\begin{document}
\section{Conclusion}
The ranking is comparative within this corpus, not an estimate over the whole literature.
\end{document}
"""
    assert not build_ledger(text).unsupported()


def test_universal_claim_still_flagged_without_negation():
    text = r"""\documentclass{article}
\begin{document}
\section{Conclusion}
No study reports a provenance metric.
\end{document}
"""
    assert build_ledger(text).unsupported()
