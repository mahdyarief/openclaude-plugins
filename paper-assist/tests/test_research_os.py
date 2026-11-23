"""End-to-end tests for the research OS pipeline and artifact separation."""

from __future__ import annotations

import json

import pytest

from paperassist.research_os import (
    RESEARCH_OS_SCHEMA,
    ResearchOSError,
    ResearchOSSafetyError,
    expand_includes,
    run_research_os,
)

PAPER = r"""\documentclass{article}
\usepackage[margin=2.5cm]{geometry}
\begin{document}
\maketitle
\begin{abstract}
This review examines whether claim tasks are addressable by automation. We searched
three databases and screened records with PRISMA, and the results show that coding
scores highest. We conclude that provenance must be reported explicitly.
\end{abstract}
\section{Introduction}
Prior work established a baseline \citep{alpha2020}.% @locator{alpha2020: page=3, quote="baseline improved"}
This paragraph only links the sections together.
\section{Method}
We searched Scopus, PubMed and IEEE with a documented search strategy, applied
inclusion and exclusion criteria, performed extraction and quality appraisal, and
used narrative synthesis. The protocol was registered and PRISMA reporting applies.
\section{Results}
\begin{table}[htbp]
\caption{Scores.}
\label{tab:score}
\begin{tabular}{lr}
\toprule
Class & Value \\
\midrule
A & 11 \\
\bottomrule
\end{tabular}
\end{table}
Table \ref{tab:score} reports values.
\section{Discussion}
The gradient has consequences for governance and audit.
\section{Limitations}
The corpus and instrument constrain generalisability.
\section{Conclusions}
Coding is the defensible target and provenance must be measured.
\end{document}
"""

BIB = """@article{alpha2020,
  title = {A Baseline Study Of Addressability},
  doi = {10.1000/alpha},
  year = {2020}
}
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.tex").write_text(PAPER, encoding="utf-8")
    (tmp_path / "paper" / "refs.bib").write_text(BIB, encoding="utf-8")
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "pdfs" / "r001.pdf").write_bytes(b"%PDF-1.4 alpha")
    (tmp_path / "records.json").write_text(
        json.dumps(
            [
                {"id": "r001", "title": "A Baseline Study Of Addressability",
                 "doi": "10.1000/alpha", "year": "2020", "authors": "Alpha, A."},
                {"id": "r002", "title": "Another Work Without A Local Copy",
                 "doi": "", "year": "2021"},
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def run(project, **overrides):
    payload = {
        "run_id": "test-run",
        "target_path": "paper/main.tex",
        "records_path": "records.json",
        "fulltext_root": "pdfs",
        "bibliography_path": "paper/refs.bib",
    }
    payload.update(overrides)
    return run_research_os(project, payload)


def test_pipeline_writes_every_artifact(project):
    result = run(project)
    root = project / result.output_dir
    for name in (
        "corpus-binding.json",
        "claim-ledger.json",
        "narrative.jsonl",
        "evidence.jsonl",
        "quality-report.json",
        "quality-report.md",
        "claim-ledger.md",
        "revision-plan.json",
        "index.md",
    ):
        assert (root / name).is_file(), name


def test_narrative_and_evidence_never_overlap(project):
    result = run(project)
    root = project / result.output_dir
    narrative = {
        json.loads(line)["claim_id"]
        for line in (root / "narrative.jsonl").read_text(encoding="utf-8").splitlines()
    }
    evidence = {
        json.loads(line)["claim_id"]
        for line in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    }
    assert narrative
    assert evidence
    assert not narrative & evidence


def test_narrative_channel_holds_no_factual_claims(project):
    result = run(project, run_id="run-narr")
    root = project / result.output_dir
    for line in (root / "narrative.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        assert record["channel"] == "narrative"
        assert record["status"] == "narrative"
        assert record["quantities"] == []


def test_evidence_channel_carries_provenance(project):
    result = run(project, run_id="run-prov")
    root = project / result.output_dir
    grounded = [
        json.loads(line)
        for line in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(record["status"] == "grounded" for record in grounded)
    for record in grounded:
        if record["status"] in {"grounded", "attributed", "derived"}:
            assert record["evidence_refs"]


def test_preamble_does_not_leak_into_claims(project):
    result = run(project, run_id="run-preamble")
    ledger = json.loads(
        (project / result.output_dir / "claim-ledger.json").read_text(encoding="utf-8")
    )
    for claim in ledger["claims"]:
        assert "margin" not in claim["sentence"]
        assert "documentclass" not in claim["sentence"]


def test_result_payload_is_serialisable(project):
    result = run(project, run_id="run-payload")
    payload = result.to_dict()
    assert payload["schema"] == RESEARCH_OS_SCHEMA
    assert payload["quality"]["score"] > 0
    json.dumps(payload)


def test_run_is_deterministic(project):
    first = run(project, run_id="run-det")
    second = run(project, run_id="run-det")
    assert first.digest == second.digest


def test_run_without_records_still_scores(project):
    result = run_research_os(
        project,
        {"run_id": "no-records", "target_path": "paper/main.tex"},
    )
    assert result.binding is None
    assert result.quality is not None
    assert (project / result.output_dir / "evidence.jsonl").is_file()


def test_missing_target_is_rejected(project):
    with pytest.raises(ResearchOSError):
        run_research_os(project, {"run_id": "x", "target_path": "nope.tex"})


def test_run_id_cannot_escape_workspace(project):
    with pytest.raises(ResearchOSError):
        run(project, run_id="../escape")


def test_target_cannot_escape_workspace(project):
    outside = project.parent / "outside.tex"
    outside.write_text(PAPER, encoding="utf-8")
    with pytest.raises(ResearchOSSafetyError):
        run_research_os(project, {"run_id": "x", "target_path": str(outside)})


def test_index_mentions_separation_contract(project):
    result = run(project, run_id="run-index")
    index = (project / result.output_dir / "index.md").read_text(encoding="utf-8")
    assert "narrative.jsonl" in index
    assert "evidence.jsonl" in index
    assert "never overlap" in index


def test_count_document_is_evidence_but_not_a_study(project):
    # A flow summary states corpus totals. Those numbers must confirm prose,
    # yet the summary itself is not one of the studies under review, so it must
    # not inflate the corpus the reporting floor is measured against, and it must
    # not become an extra record in the bibliography or catalogue.
    (project / "flow.json").write_text(
        json.dumps({"identified_total": 265, "included_total": 108, "_counts": True}),
        encoding="utf-8",
    )
    paper = PAPER.replace(
        "Coding is the defensible target",
        "Of 265 records, 108 entered synthesis; coding is the defensible target",
    )
    (project / "paper" / "main.tex").write_text(paper, encoding="utf-8")
    result = run(
        project,
        run_id="count-doc",
        records_paths=["records.json", "flow.json"],
    )
    depth = result.quality.dimension("depth")
    assert depth.measurements["corpus_records"] == 2
    assert result.quality.dimension("citations").measurements["corpus_records"] == 2
    assert result.quality.dimension("evidence").measurements["corpus_records"] == 2
    assert result.ledger.summary()["unsupported"] == 0
    assert len(result.binding.records) == 2
    catalogue = (project / result.output_dir / "study-catalogue.tex").read_text(
        encoding="utf-8"
    )
    assert catalogue.count(r"\citep{") == 2


def test_quality_report_records_em_dash_style(project):
    dashed = PAPER.replace(
        "The gradient has consequences",
        "The gradient --- and this matters --- has consequences",
    )
    (project / "paper" / "main.tex").write_text(dashed, encoding="utf-8")
    result = run(project, run_id="run-dash")
    payload = json.loads(
        (project / result.output_dir / "quality-report.json").read_text(encoding="utf-8")
    )
    style = next(d for d in payload["dimensions"] if d["name"] == "prose_style")
    assert style["measurements"]["em_dashes"] == 2


def test_input_files_are_part_of_the_manuscript(tmp_path):
    """A section written in another file still counts as manuscript prose."""

    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.tex").write_text(
        "\section{Introduction}\n" + ("word " * 600) + "\n\input{sections/appendix}\n",
        encoding="utf-8",
    )
    (tmp_path / "paper" / "sections").mkdir()
    (tmp_path / "paper" / "sections" / "appendix.tex").write_text(
        "\section{Discussion}\n" + ("analysis " * 700) + "\n", encoding="utf-8"
    )
    text = expand_includes(tmp_path / "paper" / "main.tex", tmp_path)
    assert "analysis" in text
    assert "\input{" not in text


def test_include_cycle_is_bounded(tmp_path):
    (tmp_path / "a.tex").write_text("\input{b}\n", encoding="utf-8")
    (tmp_path / "b.tex").write_text("\input{a}\n", encoding="utf-8")
    text = expand_includes(tmp_path / "a.tex", tmp_path)
    assert isinstance(text, str)
