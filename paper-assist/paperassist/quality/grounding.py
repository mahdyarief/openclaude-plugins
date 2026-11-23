"""Citations, provenance and evidence dimensions: can each claim be traced to a source?"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..claim_ledger import ClaimLedger
from ..corpus_binder import CorpusBinding
from ..reporting_checks import (
    LOCATOR_NOT_FOUND,
)
from ._base import (
    DEFAULT_WEIGHTS,
    Dimension,
    Finding,
    _clamp,
)


def _dimension_citations(
    ledger: ClaimLedger,
    binding: CorpusBinding | None,
    *,
    reference_keys: Sequence[str],
) -> Dimension:
    findings: list[Finding] = []
    cited: list[str] = []
    for claim in ledger.claims:
        for key in claim.citation_keys:
            if key not in cited:
                cited.append(key)
    known = set(reference_keys)
    unresolved = [key for key in cited if known and key not in known]
    for key in unresolved[:10]:
        findings.append(
            Finding(
                dimension="citations",
                severity="critical",
                message=f"citation key not in reference list: {key}",
                remedy="add the entry to the bibliography or remove the citation",
            )
        )
    evidence_claims = [c for c in ledger.claims if c.channel == "evidence"]
    # A derived claim is arithmetic over ingested data records, so it is already
    # traceable without a citation. Requiring one for it conflates "no source"
    # with "source is the dataset" and penalises synthesis-heavy reviews, whose
    # result sentences are mostly aggregates. Only attributed and grounded
    # claims assert something external and therefore demand a bibliography key.
    citable_claims = [c for c in evidence_claims if c.status != "derived"]
    cited_claims = sum(1 for claim in citable_claims if claim.citation_keys)
    cited_share = cited_claims / len(citable_claims) if citable_claims else 1.0
    reference_count = len(reference_keys) or len(cited)
    corpus_size = len(binding.records) if binding else 0
    coverage = binding.coverage()["bibliography_coverage"] if binding and corpus_size else 0.0
    if corpus_size and coverage < 0.25:
        findings.append(
            Finding(
                dimension="citations",
                severity="critical",
                message=(
                    f"only {coverage:.1%} of {corpus_size} extracted records have a "
                    "bibliography entry"
                ),
                remedy=(
                    "generate bibliography entries for the full evidence corpus; a "
                    "review citing a small fraction of its records is not auditable"
                ),
            )
        )
    if corpus_size:
        score = (
            0.35 * cited_share
            + 0.25 * min(1.0, reference_count / 40)
            + 0.40 * min(1.0, coverage / 0.8)
        )
    else:
        score = 0.5 * cited_share + 0.5 * min(1.0, reference_count / 40)
    if unresolved:
        score *= 0.8
    return Dimension(
        name="citations",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["citations"],
        measurements={
            "cited_keys": len(set(cited)),
            "reference_entries": reference_count,
            # Derived claims are excluded from both sides, as in the score.
            "citable_claims_with_citation": f"{cited_claims}/{len(citable_claims)}",
            "corpus_records": corpus_size,
            "corpus_coverage": round(coverage, 4),
            "unresolved_keys": unresolved,
        },
        findings=tuple(findings),
    )


def _dimension_provenance(
    ledger: ClaimLedger,
    *,
    min_anchored: float,
    locator_checks: Mapping[str, str] | None = None,
) -> Dimension:
    summary = ledger.summary()
    evidence = summary["evidence_channel"]
    anchored = summary["grounded"] + summary["attributed"] + summary["derived"]
    findings: list[Finding] = []
    # A locator whose quote does not occur in the cited work's own text anchors
    # nothing: it reads as provenance while pointing at words that are not there.
    failed_keys = {
        key for key, status in (locator_checks or {}).items() if status == LOCATOR_NOT_FOUND
    }
    contradicted = [
        claim
        for claim in ledger.claims
        if claim.status == "grounded"
        and claim.locator_keys
        and all(key in failed_keys for key in claim.locator_keys)
    ]
    if contradicted:
        anchored -= len(contradicted)
        findings.append(
            Finding(
                dimension="provenance",
                severity="critical",
                message=(
                    f"{len(contradicted)} grounded sentence(s) cite a locator quote that "
                    "does not occur in the bound full text: "
                    + ", ".join(sorted(failed_keys)[:5])
                ),
                remedy="copy the quote verbatim from the source, or fix the locator key",
                line=contradicted[0].line_start,
            )
        )
    ratio = anchored / evidence if evidence else 1.0
    unsupported = summary["unsupported"]
    if unsupported:
        findings.append(
            Finding(
                dimension="provenance",
                severity="critical",
                message=(
                    f"{unsupported} quantitative assertion(s) have no locator, "
                    "citation or data record"
                ),
                remedy="anchor each number to a locator, a citation or an ingested data record",
            )
        )
    if evidence and ratio < min_anchored:
        findings.append(
            Finding(
                dimension="provenance",
                severity="critical",
                message=(
                    f"anchored evidence ratio {ratio:.1%} is below the "
                    f"{min_anchored:.0%} floor"
                ),
                remedy=(
                    'add `% @locator{key: page=.., quote=".."}` annotations with '
                    "verbatim excerpts"
                ),
            )
        )
    if evidence and summary["grounded"] == 0:
        findings.append(
            Finding(
                dimension="provenance",
                severity="warning",
                message="no sentence is grounded in a verbatim source excerpt",
                remedy=(
                    "extract excerpts for the cited works and annotate the sentence "
                    "that uses each"
                ),
            )
        )
    score = ratio
    if unsupported:
        score *= 1 - min(0.5, unsupported / max(1, len(ledger.claims)) * 2)
    return Dimension(
        name="provenance",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["provenance"],
        measurements={
            "evidence_claims": evidence,
            "anchored": anchored,
            "grounded": summary["grounded"],
            "attributed": summary["attributed"],
            "derived": summary["derived"],
            "unsupported": unsupported,
            "anchored_ratio": round(ratio, 4),
            "ledger_anchored_ratio": summary["anchored_ratio"],
            "locator_quotes": dict(locator_checks) if locator_checks else None,
            "locator_quotes_not_found": sorted(failed_keys),
        },
        findings=tuple(findings),
    )


def _dimension_evidence(
    ledger: ClaimLedger, binding: CorpusBinding | None
) -> Dimension:
    summary = ledger.summary()
    findings: list[Finding] = []
    total = len(ledger.claims)
    evidence_share = summary["evidence_channel"] / total if total else 0.0
    if total and evidence_share < 0.3:
        findings.append(
            Finding(
                dimension="evidence",
                severity="critical",
                message=(
                    f"only {evidence_share:.1%} of sentences make a verifiable assertion"
                ),
                remedy=(
                    "replace procedural narration with sourced findings; a review "
                    "must report evidence, not process"
                ),
            )
        )
    corpus_size = len(binding.records) if binding else 0
    coverage = binding.coverage() if binding and corpus_size else None
    if coverage and coverage["text_coverage"] < 0.5:
        findings.append(
            Finding(
                dimension="evidence",
                severity="warning",
                message=(
                    f"only {coverage['text_coverage']:.1%} of records have a local "
                    "full text"
                ),
                remedy=(
                    "bind extraction records to the full-text corpus so quotes can "
                    "be verified"
                ),
            )
        )
    score = 0.6 * min(1.0, evidence_share / 0.6)
    if coverage:
        score += 0.4 * min(1.0, coverage["text_coverage"] / 0.9)
    else:
        score += 0.4 * min(
            1.0, summary["derived"] / max(1, summary["evidence_channel"]) / 0.3
        )
    if summary["unsupported"]:
        score *= 0.85
    return Dimension(
        name="evidence",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["evidence"],
        measurements={
            "claims": total,
            "evidence_share": round(evidence_share, 4),
            "derived": summary["derived"],
            "corpus_records": corpus_size,
            "corpus_text_coverage": (
                coverage["text_coverage"] if coverage else None
            ),
        },
        findings=tuple(findings),
    )
