"""End-to-end research pipeline: bind, audit, score, separate, plan.

This module is the composition point. It runs the deterministic stages in the
order a reviewer would: bind the evidence corpus, split the manuscript into a
sourced channel and a narrative channel, score the manuscript, and produce a
revision plan. Every stage writes its own artifact so the AI narrative can be
inspected beside the evidence rather than inside it.

Artifacts written under ``.paperassist/research-os/<run_id>/``:

``corpus-binding.json``
    Which records have a full text and a bibliography entry.
``narrative.jsonl``
    Model prose: sentences that assert nothing verifiable. Safe to rewrite.
``evidence.jsonl``
    Sourced substance: each claim with its locator, citation or data record.
``claim-ledger.json``
    Both channels plus the summary and digests.
``quality-report.json`` / ``quality-report.md``
    Dimension scores, grade and actionable findings.
``revision-plan.json``
    Findings ordered by severity and weighted impact.
``index.md``
    Human-readable entry point linking the artifacts above.

Nothing in this module calls a language model. The harness reads these
artifacts, revises, and submits the result to ``verify_revision``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .claim_ledger import (
    CHANNEL_EVIDENCE,
    CHANNEL_NARRATIVE,
    ClaimLedger,
    build_ledger,
    format_ledger_report,
)
from .corpus_binder import (
    CorpusBinding,
    assign_bibtex_keys,
    bind_corpus,
    enrich_records_with_ris,
    format_binding_report,
    parse_ris,
    render_study_catalogue,
)
from .improvement_loop import revision_plan
from .manuscript_quality import (
    QualityError,
    QualityReport,
    format_quality_report,
    score_manuscript,
)
from .participant_flow import ARM_KEYS, check_participant_flow
from .path_safety import UnsafePathError, reject_symlink_components
from .provenance_audit import DEFAULT_MIN_ANCHORED, extract_locators, load_locators_payload
from .quality.scoring import DEFAULT_DEPTH_TARGET, thesis_reference_policy
from .reporting_checks import (
    ReferencePolicy,
    audit_references,
    check_declarations,
    check_prisma_flow,
    cited_keys,
    load_retraction_dois,
    resolve_paper_type,
    resolve_research_design,
    verify_locator_quotes,
)
from .research_designs import explain_detection
from .source_coverage import SourceCoverage, audit_source_coverage, format_source_coverage
from .thesis_checks import check_thesis, resolve_document_kind

RESEARCH_OS_ROOT = Path(".paperassist") / "research-os"
RESEARCH_OS_SCHEMA = "paperassist.research-os/v1"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ResearchOSError(RuntimeError):
    pass


class ResearchOSSafetyError(ResearchOSError):
    pass


@dataclass(frozen=True)
class ResearchOSResult:
    run_id: str
    output_dir: str
    binding: CorpusBinding | None = None
    ledger: ClaimLedger | None = None
    quality: QualityReport | None = None
    plan: tuple[Mapping[str, Any], ...] = ()
    artifacts: Mapping[str, str] = field(default_factory=dict)
    digest: str = ""
    source_coverage: SourceCoverage | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESEARCH_OS_SCHEMA,
            "run_id": self.run_id,
            "output_dir": self.output_dir,
            "digest": self.digest,
            "artifacts": dict(self.artifacts),
            "corpus": self.binding.coverage() if self.binding else None,
            "ledger": self.ledger.summary() if self.ledger else None,
            "quality": (
                {
                    "score": round(self.quality.score, 4),
                    "grade": self.quality.grade,
                    "recommendation": self.quality.recommendation,
                    "worst_dimensions": list(self.quality.worst_dimensions),
                }
                if self.quality
                else None
            ),
            "revision_plan": [dict(item) for item in self.plan],
            "source_coverage": (
                self.source_coverage.to_dict() if self.source_coverage else None
            ),
        }


def _resolve_run_dir(workspace: Path, run_id: str) -> Path:
    if not _RUN_ID_RE.match(run_id):
        raise ResearchOSError(
            "run_id must be 1-64 characters of letters, digits, dot, dash or underscore"
        )
    root = (workspace / RESEARCH_OS_ROOT / run_id).resolve()
    if not root.is_relative_to(workspace):
        raise ResearchOSSafetyError("run directory escapes the workspace")
    try:
        reject_symlink_components(root, anchor=workspace)
    except UnsafePathError as exc:
        raise ResearchOSSafetyError(f"run directory is unsafe: {exc}") from exc
    return root


def _resolve_source(workspace: Path, raw: str | Path, *, what: str) -> Path:
    supplied = Path(str(raw)).expanduser()
    lexical = supplied if supplied.is_absolute() else workspace / supplied
    try:
        lexical = reject_symlink_components(lexical, anchor=workspace)
    except UnsafePathError as exc:
        raise ResearchOSSafetyError(f"{what} is unsafe: {raw} ({exc})") from exc
    if not lexical.is_file():
        raise ResearchOSError(f"{what} not found: {raw}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace):
        raise ResearchOSSafetyError(f"{what} escapes the workspace: {raw}")
    return resolved


def read_workspace_text(
    workspace: str | Path, raw: str | Path, *, what: str = "file"
) -> str:
    """Read a workspace-contained UTF-8 file, refusing any path escape."""

    root = Path(workspace).expanduser().resolve(strict=True)
    path = _resolve_source(root, raw, what=what)
    return path.read_text(encoding="utf-8", errors="replace")


def _read_records_file(workspace: Path, source: str) -> list[Mapping[str, Any]]:
    path = _resolve_source(workspace, source, what="records file")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ResearchOSError(f"records file is not valid JSON: {source}") from exc
    if isinstance(data, Mapping):
        for key in ("records", "data", "items", "results", "unique"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            # A count document (screening totals, a flow summary) is still
            # evidence: its numbers are what the prose cites. A document of
            # records, by contrast, always holds its rows in a list.
            # Trial arms listed as objects are counts too, not study rows.
            if not any(
                isinstance(value, list) and value and isinstance(value[0], Mapping)
                for key, value in data.items()
                if str(key).strip().lower() not in ARM_KEYS
            ):
                # Marking the document tells the ledger its numbers are counts
                # and proportions, not measurements. Without the marker the
                # flow totals would only be readable as bare digits, and
                # "265 rekaman" would find nothing to rest on.
                tagged = dict(data)
                tagged["_counts"] = True
                return [tagged]
    if not isinstance(data, list):
        raise ResearchOSError("records file must contain a JSON array of objects")
    return [record for record in data if isinstance(record, Mapping)]


def _load_records(
    workspace: Path, payload: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Load every declared evidence source as one record list.

    A review's traceable numbers rarely live in a single file: study rows sit
    in the extraction table while screening flow counts sit beside them.
    Accepting a list of sources lets all of them count as evidence rather than
    forcing the prose to be scored against one narrow file.
    """

    inline = payload.get("records")
    if isinstance(inline, Sequence) and not isinstance(inline, (str, bytes)):
        return [record for record in inline if isinstance(record, Mapping)]

    sources = payload.get("records_paths")
    if isinstance(sources, str):
        sources = [sources]
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        sources = []
    primary = payload.get("records_path") or payload.get("extraction_path")
    declared = [str(item) for item in sources if str(item).strip()]
    if primary:
        declared.insert(0, str(primary))
    if not declared:
        return []

    merged: list[Mapping[str, Any]] = []
    for source in dict.fromkeys(declared):
        for record in _read_records_file(workspace, source):
            # Aggregates are computed per source, so each record has to carry
            # the file it came from. Without this the screening corpus and the
            # extraction table would share one denominator.
            tagged = dict(record)
            tagged.setdefault("_source", source)
            merged.append(tagged)

    ris_sources = payload.get("ris_paths")
    if isinstance(ris_sources, str):
        ris_sources = [ris_sources]
    if isinstance(ris_sources, Sequence) and not isinstance(ris_sources, (str, bytes)):
        ris_records: list[dict[str, Any]] = []
        for source in ris_sources:
            path = _resolve_source(workspace, str(source), what="RIS source")
            ris_records.extend(parse_ris(path.read_text(encoding="utf-8", errors="replace")))
        if ris_records:
            enriched, _ = enrich_records_with_ris(merged, ris_records)
            merged[:] = enriched
    return merged


_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def expand_includes(path: Path, root: Path, *, depth: int = 0) -> str:
    """Read a manuscript with its ``\\input`` and ``\\include`` files inlined.

    A manuscript split into per-section files is still one manuscript. Scoring
    only the root file would judge a paper by its preamble and silently ignore
    every section written elsewhere, including a generated appendix that
    carries the citation keys. Includes resolve relative to the including file
    first, then to the project root, and are capped in depth so a cycle cannot
    recurse forever.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    if depth >= 8:
        return text

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if not name or "\\" in name or name.startswith("/"):
            return match.group(0)
        candidates = [path.parent / name]
        if not name.lower().endswith(".tex"):
            candidates = [candidate.with_suffix(".tex") for candidate in candidates]
        candidates.append(root / name)
        for candidate in candidates:
            if candidate.is_file():
                return expand_includes(candidate, root, depth=depth + 1)
        return match.group(0)

    return _INCLUDE_RE.sub(replace, text)


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.as_posix()


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


_TEXT_SUFFIXES = (".txt", ".md", ".tex")
_LOCATOR_TEXT_BUDGET = 4_000_000


def _bound_texts(
    root: Path, payload: Mapping[str, Any], binding: CorpusBinding | None
) -> dict[str, str]:
    """Full text per bibliography key, for verifying locator quotes."""

    if binding is None:
        return {}
    fulltext = payload.get("fulltext_root") or payload.get("pdf_root")
    if not fulltext:
        return {}
    base = (root / str(fulltext)).resolve()
    if not base.is_relative_to(root):
        return {}
    texts: dict[str, str] = {}
    for record in binding.records:
        if not (record.bib_key and record.text_path):
            continue
        path = (base / record.text_path).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in _TEXT_SUFFIXES:
                texts[record.bib_key] = path.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".pdf":
                from .references import _extract_pdf

                body, *_ = _extract_pdf(path.read_bytes(), budget_bytes=_LOCATOR_TEXT_BUDGET)
                if body.strip():
                    texts[record.bib_key] = body
        except OSError:
            continue
    return texts


def _participant_flow_documents(
    root: Path, payload: Mapping[str, Any], count_documents: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """The CONSORT/STROBE counts: ``participant_flow`` (object or JSON path) or count files."""

    value = payload.get("participant_flow")
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, str) and value.strip():
        path = _resolve_source(root, value, what="participant flow")
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ResearchOSError(f"participant flow is not valid JSON: {value}") from exc
        if not isinstance(data, Mapping):
            raise ResearchOSError("participant flow must be a JSON object of counts")
        return [data]
    if value not in (None, ""):
        raise ResearchOSError("participant_flow must be a JSON object or a workspace path")
    return list(count_documents)


def _reporting_checks(
    root: Path,
    payload: Mapping[str, Any],
    *,
    manuscript: str,
    records: Sequence[Mapping[str, Any]],
    study_count: int,
    bibliography_text: str | None,
    binding: CorpusBinding | None,
    locators: Sequence[Any] | None,
) -> dict[str, Any]:
    """Run the reporting-standard checks and return their results by name."""

    try:
        paper_type = resolve_paper_type(
            payload.get("paper_type"), manuscript, study_count=study_count
        )
        design = resolve_research_design(
            payload.get("research_design"),
            manuscript,
            study_count=study_count,
            paper_type=payload.get("paper_type"),
        )
    except ValueError as exc:
        raise ResearchOSError(str(exc)) from exc
    explicit_design = payload.get("research_design") not in (None, "", "auto")
    if explicit_design:
        paper_type = design.family

    count_documents = [record for record in records if record.get("_counts")]
    flow = check_prisma_flow(count_documents)
    participant_flow = None
    if design.flow in ("consort", "strobe"):
        participant_flow = check_participant_flow(
            _participant_flow_documents(root, payload, count_documents),
            kind=design.flow,
            randomised=design.key == "rct",
        )

    required = payload.get("required_declarations")
    profile_id = payload.get("journal_profile")
    if required is None and profile_id:
        from .journal_profiles import PROFILES

        profile = next((p for p in PROFILES if p.profile_id == profile_id), None)
        if profile is None:
            raise ResearchOSError(f"unknown journal_profile: {profile_id}")
        required = list(profile.required_declarations) or None
    try:
        declarations = check_declarations(
            manuscript, required=required, paper_type=paper_type
        )
        policy = ReferencePolicy.from_payload(payload.get("reference_policy"))
    except (TypeError, ValueError) as exc:
        raise ResearchOSError(str(exc)) from exc

    retractions = None
    if payload.get("retraction_db_path"):
        csv_path = _resolve_source(root, payload["retraction_db_path"], what="retraction database")
        try:
            retractions = load_retraction_dois(
                csv_path.read_text(encoding="utf-8", errors="replace")
            )
        except ValueError as exc:
            raise ResearchOSError(str(exc)) from exc

    try:
        document_kind = resolve_document_kind(payload.get("document_kind"), manuscript)
        thesis = (
            check_thesis(
                manuscript,
                profile=payload.get("thesis_profile") or "auto",
                required_front_matter_items=payload.get("required_front_matter"),
                stage=payload.get("thesis_stage") or "auto",
            )
            if document_kind == "thesis"
            else None
        )
    except ValueError as exc:
        raise ResearchOSError(str(exc)) from exc

    if not payload.get("reference_policy") and thesis is not None:
        # The campus guide's reference rule, when its profile states one.
        policy = thesis_reference_policy(thesis) or policy

    reference_audit = None
    if bibliography_text:
        from .corpus_binder import parse_bib_entries

        cited = cited_keys(manuscript)
        reference_audit = audit_references(
            parse_bib_entries(bibliography_text),
            cited_keys=cited,
            policy=policy,
            retractions=retractions,
        )

    locator_checks = None
    texts = _bound_texts(root, payload, binding)
    if locators and texts:
        locator_checks = verify_locator_quotes(locators, texts)

    return {
        "paper_type": paper_type,
        "research_design": design,
        "prisma_flow": flow if design.flow == "prisma" else None,
        "participant_flow": participant_flow,
        "design_detection": None
        if explicit_design
        else explain_detection(manuscript, family=design.family),
        "declarations": declarations,
        "reference_audit": reference_audit,
        "locator_checks": locator_checks,
        "document_kind": document_kind,
        "thesis": thesis,
    }


def run_research_os(
    workspace: str | Path,
    payload: Mapping[str, Any],
) -> ResearchOSResult:
    """Run the full deterministic pipeline and write separated artifacts."""

    root = Path(workspace).expanduser().resolve(strict=True)
    run_id = str(payload.get("run_id") or "run").strip()
    target = payload.get("target_path") or payload.get("manuscript_path")
    if not target:
        raise ResearchOSError("research OS requires `target_path`")
    manuscript_path = _resolve_source(root, target, what="manuscript")
    manuscript = expand_includes(manuscript_path, root)
    if not manuscript.strip():
        raise ResearchOSError("manuscript is empty")

    records = _load_records(root, payload)
    study_records = [record for record in records if not record.get("_counts")]

    locators = None
    if payload.get("locators") is not None or payload.get("locators_payload") is not None:
        locators = load_locators_payload(
            payload.get("locators")
            if payload.get("locators") is not None
            else payload.get("locators_payload")
        )
    else:
        locators = extract_locators(manuscript)

    binding: CorpusBinding | None = None
    if records and (payload.get("fulltext_root") or payload.get("pdf_root")):
        binding = bind_corpus(
            root,
            {
                "records": study_records,
                "fulltext_root": payload.get("fulltext_root") or payload.get("pdf_root"),
                "bibliography_path": payload.get("bibliography_path"),
            },
        )

    ledger = build_ledger(manuscript, locators=locators, records=records)

    bibliography_entries: list[str] = []
    bibliography_text: str | None = None
    if payload.get("bibliography_path"):
        bib_path = _resolve_source(root, payload["bibliography_path"], what="bibliography")
        bibliography_text = bib_path.read_text(encoding="utf-8", errors="replace")
        from .corpus_binder import parse_bib_entries

        bibliography_entries = [entry.key for entry in parse_bib_entries(bibliography_text)]

    # A flow document reports totals; the records beside it are the studies the
    # review had to account for. Counting the flow document as a study would
    # size the reporting floor off the wrong number.
    study_count = len(study_records)

    checks = _reporting_checks(
        root,
        payload,
        manuscript=manuscript,
        records=records,
        study_count=study_count,
        bibliography_text=bibliography_text,
        binding=binding,
        locators=locators,
    )

    try:
        quality = score_manuscript(
            manuscript,
            ledger=ledger,
            binding=binding,
            bibliography_entries=bibliography_entries,
            bibliography_text=bibliography_text,
            depth_target=int(payload.get("depth_target") or DEFAULT_DEPTH_TARGET),
            min_anchored=float(payload.get("min_anchored") or DEFAULT_MIN_ANCHORED),
            allow_em_dash=bool(payload.get("allow_em_dash", False)),
            corpus_size=study_count,
            paper_type=checks["paper_type"],
            research_design=checks["research_design"].key,
            prisma_flow=checks["prisma_flow"],
            participant_flow=checks["participant_flow"],
            declarations=checks["declarations"],
            reference_audit=checks["reference_audit"],
            locator_checks=checks["locator_checks"],
            asset_root=str(manuscript_path.parent),
            document_kind=checks["document_kind"],
            thesis=checks["thesis"],
        )
    except QualityError as exc:
        raise ResearchOSError(str(exc)) from exc

    plan = revision_plan(quality, limit=int(payload.get("plan_limit") or 8))

    coverage: SourceCoverage | None = None
    source_target = payload.get("source_path") or payload.get("research_source")
    if source_target:
        source_path = _resolve_source(root, source_target, what="research source")
        try:
            coverage = audit_source_coverage(
                source_path.read_text(encoding="utf-8", errors="replace"),
                manuscript,
            )
        except ValueError as exc:
            raise ResearchOSError(str(exc)) from exc

    output_dir = _resolve_run_dir(root, run_id)
    artifacts: dict[str, str] = {}

    if binding is not None:
        artifacts["corpus_binding"] = _write(
            output_dir / "corpus-binding.json", _json(binding.to_dict())
        )
        _write(output_dir / "corpus-binding.md", format_binding_report(binding))

        key_by_id, bib_text, bib_warnings = assign_bibtex_keys(
            binding, study_records
        )
        catalogue, catalogue_warnings = render_study_catalogue(
            binding, study_records, key_by_id=key_by_id
        )
        artifacts["corpus_bibliography"] = _write(
            output_dir / "corpus-bibliography.bib", bib_text
        )
        artifacts["study_catalogue"] = _write(
            output_dir / "study-catalogue.tex", catalogue
        )
        binding_sidecar = {
            "bibliography_keys": key_by_id,
            "bibtex_warnings": list(bib_warnings),
            "catalogue_warnings": list(catalogue_warnings),
        }
        artifacts["corpus_sidecar"] = _write(
            output_dir / "corpus-sidecar.json", _json(binding_sidecar)
        )

    artifacts["claim_ledger"] = _write(
        output_dir / "claim-ledger.json", _json(ledger.to_dict())
    )
    artifacts["narrative"] = _write(
        output_dir / "narrative.jsonl", ledger.to_jsonl(CHANNEL_NARRATIVE)
    )
    artifacts["evidence"] = _write(
        output_dir / "evidence.jsonl", ledger.to_jsonl(CHANNEL_EVIDENCE)
    )
    artifacts["quality_json"] = _write(
        output_dir / "quality-report.json", _json(quality.to_dict())
    )
    artifacts["quality_md"] = _write(
        output_dir / "quality-report.md", format_quality_report(quality)
    )
    artifacts["ledger_md"] = _write(
        output_dir / "claim-ledger.md", format_ledger_report(ledger)
    )
    artifacts["revision_plan"] = _write(
        output_dir / "revision-plan.json", _json({"plan": list(plan)})
    )
    artifacts["reporting_checks"] = _write(
        output_dir / "reporting-checks.json",
        _json(
            {
                "paper_type": checks["paper_type"],
                "document_kind": checks["document_kind"],
                "thesis": checks["thesis"].to_dict() if checks["thesis"] else None,
                "research_design": checks["research_design"].to_dict(),
                "prisma_flow": checks["prisma_flow"].to_dict()
                if checks["prisma_flow"]
                else None,
                "participant_flow": checks["participant_flow"].to_dict()
                if checks["participant_flow"]
                else None,
                "design_detection": checks["design_detection"],
                "declarations": checks["declarations"].to_dict(),
                "references": checks["reference_audit"].to_dict()
                if checks["reference_audit"]
                else None,
                "locator_quotes": checks["locator_checks"],
            }
        ),
    )

    if coverage is not None:
        artifacts["source_coverage"] = _write(
            output_dir / "source-coverage.json", _json(coverage.to_dict())
        )
        artifacts["source_coverage_md"] = _write(
            output_dir / "source-coverage.md", format_source_coverage(coverage)
        )
        if coverage.missing or coverage.partial or coverage.unaccounted_numbers:
            artifacts["revision_plan"] = _write(
                output_dir / "revision-plan.json",
                _json({
                    "plan": list(plan),
                    "source_gaps": _coverage_gaps(coverage),
                }),
            )

    index = _render_index(
        run_id=run_id,
        manuscript=manuscript_path.relative_to(root).as_posix(),
        binding=binding,
        ledger=ledger,
        quality=quality,
        plan=plan,
        artifacts=artifacts,
        root=root,
        coverage=coverage,
    )
    artifacts["index"] = _write(output_dir / "index.md", index)

    result = ResearchOSResult(
        run_id=run_id,
        output_dir=output_dir.relative_to(root).as_posix(),
        binding=binding,
        ledger=ledger,
        quality=quality,
        plan=plan,
        artifacts=artifacts,
        source_coverage=coverage,
    )
    digest = hashlib.sha256(
        json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return ResearchOSResult(
        run_id=run_id,
        output_dir=result.output_dir,
        binding=binding,
        ledger=ledger,
        quality=quality,
        plan=plan,
        artifacts=artifacts,
        digest=digest,
        source_coverage=coverage,
    )


def _coverage_gaps(coverage: SourceCoverage) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for finding in (*coverage.missing, *coverage.partial):
        gaps.append(
            {
                "section": finding.section,
                "status": finding.status,
                "message": finding.message,
                "expected_numbers": list(finding.expected_numbers),
                "found_numbers": list(finding.found_numbers),
            }
        )
    if coverage.unaccounted_numbers:
        gaps.append(
            {
                "section": "manuscript",
                "status": "unaccounted_numbers",
                "message": "Numbers asserted in the research source do not appear in the manuscript",
                "expected_numbers": [],
                "found_numbers": list(coverage.unaccounted_numbers),
            }
        )
    return gaps


def _render_index(
    *,
    run_id: str,
    manuscript: str,
    binding: CorpusBinding | None,
    ledger: ClaimLedger,
    quality: QualityReport,
    plan: Sequence[Mapping[str, Any]],
    artifacts: Mapping[str, str],
    root: Path,
    coverage: SourceCoverage | None = None,
) -> str:
    summary = ledger.summary()
    lines = [
        f"# Research OS run `{run_id}`",
        "",
        f"- manuscript: `{manuscript}`",
        f"- quality: **{quality.score:.3f}** (grade {quality.grade}, {quality.recommendation})",
        f"- claims: {summary['claims']} — evidence {summary['evidence_channel']}, "
        f"narrative {summary['narrative_channel']}",
        f"- quantitative assertions without a source: {summary['unsupported']}",
    ]
    if binding is not None:
        corpus = binding.coverage()
        lines.append(
            f"- corpus: {corpus['records']} records, "
            f"{corpus['text_coverage']:.1%} with full text, "
            f"{corpus['bibliography_coverage']:.1%} with a bibliography entry"
        )
    if coverage is not None:
        verdict = "PASS" if coverage.passed else "FAIL"
        lines.append(
            f"- source coverage: **{verdict}** "
            f"({coverage.covered_count} covered, {coverage.partial_count} partial, "
            f"{coverage.missing_count} missing, "
            f"{coverage.unaccounted_count} unaccounted numbers)"
        )
    lines += [
        "",
        "## Artifacts",
        "",
    ]
    for name, path in sorted(artifacts.items()):
        lines.append(f"- `{Path(path).name}` — {name}")
    lines += [
        "",
        "## Separation",
        "",
        "`narrative.jsonl` holds sentences that assert nothing verifiable; a harness",
        "may rewrite them freely. `evidence.jsonl` holds sourced substance; editing",
        "those sentences requires updating the locator, citation or data record they",
        "rest on. The two files never overlap, so a reviewer can diff narrative",
        "changes without touching the evidence channel.",
        "",
        "## Next actions",
        "",
    ]
    for item in plan:
        lines.append(
            f"- [{item['severity']}] {item['dimension']}: {item['message']} — {item['remedy']}"
        )
    if coverage is not None:
        gaps = _coverage_gaps(coverage)
        if gaps:
            lines += ["", "## Source gaps", ""]
            for gap in gaps:
                lines.append(f"- [{gap['status']}] {gap['section']}: {gap['message']}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "RESEARCH_OS_ROOT",
    "RESEARCH_OS_SCHEMA",
    "ResearchOSError",
    "ResearchOSResult",
    "ResearchOSSafetyError",
    "run_research_os",
]
