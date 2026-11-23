from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from mcp_servers.base import (
    BasePaperAssistMcpServer,
    ResourceSpec,
    ToolSpec,
    reject_unknown_keys,
)
from paperassist.agent_packs import (
    KIND_EXPERIMENT,
    KIND_IDEATION,
    KIND_REVIEW,
    build_experiment_pack,
    build_ideation_pack,
    build_review_pack,
    import_experiment,
    import_ideation,
    import_review,
    load_plan,
    load_task,
)
from paperassist.claim_ledger import build_ledger, format_ledger_report
from paperassist.corpus_binder import (
    bind_corpus,
    format_binding_report,
    generate_bibtex,
    load_records,
)
from paperassist.harness import harness_status
from paperassist.improvement_loop import format_verdict, revision_plan, verify_revision
from paperassist.journal_profiles import (
    PROFILE_SCHEMA,
    detect_profiles,
    format_profile_report,
    list_profiles,
    lookup_profiles,
)
from paperassist.manuscript_quality import format_quality_report, score_manuscript
from paperassist.provenance_audit import extract_locators
from paperassist.research_os import read_workspace_text, run_research_os
from paperassist.thesis_profiles import (
    THESIS_PROFILE_SCHEMA,
    detect_thesis_profiles,
    format_thesis_profile_report,
    list_thesis_profiles,
    lookup_thesis_profiles,
)

_KINDS = (KIND_IDEATION, KIND_REVIEW, KIND_EXPERIMENT)
_BUILDERS = {
    KIND_IDEATION: build_ideation_pack,
    KIND_REVIEW: build_review_pack,
    KIND_EXPERIMENT: build_experiment_pack,
}
_IMPORTERS = {
    KIND_IDEATION: import_ideation,
    KIND_REVIEW: import_review,
    KIND_EXPERIMENT: import_experiment,
}
_INPUT_KEYS = frozenset(
    {
        "topic",
        "venue",
        "constraints",
        "num_ideas",
        "manuscript",
        "main_tex",
        "hypothesis",
        "dataset",
        "metrics",
        "success_criteria",
        "bibliography_path",
    }
)

_RESEARCH_KEYS = frozenset(
    {
        "target_path",
        "manuscript_path",
        "records",
        "records_path",
        "records_paths",
        "ris_paths",
        "extraction_path",
        "fulltext_root",
        "pdf_root",
        "bibliography_path",
        "locators",
        "locators_payload",
        "depth_target",
        "min_anchored",
        "allow_em_dash",
        "plan_limit",
        "run_id",
        "source_path",
        "research_source",
        "paper_type",
        "research_design",
        "participant_flow",
        "required_declarations",
        "journal_profile",
        "reference_policy",
        "retraction_db_path",
        "document_kind",
        "thesis_profile",
        "required_front_matter",
        "thesis_stage",
    }
)


def _workspace(value: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("workspace must be a directory")
    return path


def _kind(value: str) -> str:
    kind = str(value or "").strip().lower()
    if kind not in _KINDS:
        raise ValueError("kind must be one of " + ", ".join(_KINDS))
    return kind


def _payload_locators(raw: list[dict[str, Any]]) -> list[Any]:
    from paperassist.provenance_audit import load_locators_payload

    return load_locators_payload({"locators": raw})


def _default_run_id(kind: str, inputs: dict[str, Any]) -> str:
    canonical = json.dumps({"kind": kind, "inputs": inputs}, ensure_ascii=False, sort_keys=True, default=str)
    return f"{kind}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}"


class PaperAssistMcpServer(BasePaperAssistMcpServer):
    """Model-free research tools for an external AI harness.

    Every tool builds or validates deterministic artifacts. None of them call a
    language model, and none accept credentials.
    """

    server_name = "paperassist"

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="harness_status",
                description=(
                    "Report whether the AI harness, plugin manifest, MCP servers and "
                    "LaTeX tools are ready. Replaces provider/credential preflight."
                ),
            ),
            ToolSpec(
                name="pack_scaffold",
                description=(
                    "Build an ideation, review or experiment task pack (plan, brief, "
                    "tasks, editable target) for the harness to execute. kind is "
                    "ideation, review or experiment; writing packs use writing_pack."
                ),
                payload_keys=tuple(sorted(_INPUT_KEYS)),
            ),
            ToolSpec(name="pack_plan", description="Read one pack plan."),
            ToolSpec(name="pack_task", description="Read one task file from a pack."),
            ToolSpec(
                name="pack_import",
                description=(
                    "Validate a harness-produced JSON result against the pack gates "
                    "and record it in the workspace."
                ),
            ),
            ToolSpec(
                name="corpus_bind",
                description=(
                    "Bind extracted study records to local full texts and bibliography "
                    "entries by DOI, title and record id; report citation coverage and "
                    "emit BibTeX for uncited records."
                ),
            ),
            ToolSpec(
                name="claim_audit",
                description=(
                    "Split a manuscript into a sourced evidence channel and a model "
                    "narrative channel, with locator/citation/data-record provenance "
                    "per sentence."
                ),
            ),
            ToolSpec(
                name="quality_score",
                description=(
                    "Score a manuscript across structure, abstract, depth, citations, "
                    "provenance, evidence, method rigour, limitations, prose style, "
                    "declarations, references, figures, readability and (advisory) "
                    "formulaic prose; research_design (or paper_type) selects the "
                    "reporting standard: PRISMA, CONSORT, STROBE, CROSS, SRQR/COREQ, "
                    "TRIPOD+AI, REFORMS, DSRM, R&D, PTK and more. document_kind=thesis "
                    "(or auto) checks thesis front matter, Chapter 1, question-objective-"
                    "conclusion alignment and layout against thesis_profile. Returns a "
                    "grade and blocking findings."
                ),
            ),
            ToolSpec(
                name="research_os",
                description=(
                    "Run the full pipeline (bind, audit, score, separate, plan) and "
                    "write narrative.jsonl and evidence.jsonl as distinct artifacts; "
                    "also checks flow arithmetic (PRISMA for reviews, CONSORT/STROBE "
                    "participant flow for trials and observational studies), "
                    "declarations, references "
                    "(recency, primary share, retractions) and locator quotes."
                ),
                payload_keys=tuple(sorted(_RESEARCH_KEYS)),
            ),
            ToolSpec(
                name="improvement_verify",
                description=(
                    "Compare a revision against its baseline and refuse regressions in "
                    "grounding, unsupported assertions, citations or required sections."
                ),
            ),
            ToolSpec(
                name="journal_lookup",
                description=(
                    "Look up curated journal/profile format references (Indonesian "
                    "SINTA/JTIM and international Elsevier/IEEE/Springer/ACM), or "
                    "detect plausible profiles from LaTeX source; returns abstract "
                    "layout notes and citable sources."
                ),
            ),
            ToolSpec(
                name="thesis_lookup",
                description=(
                    "Look up curated thesis/dissertation formatting profiles "
                    "(Indonesian campus guidelines such as Telkom, plus generic "
                    "skripsi/tesis baselines), or detect plausible profiles from "
                    "LaTeX source; returns margin/font/spacing/pagination rules "
                    "and a ready-to-use LaTeX preamble."
                ),
            ),
            ToolSpec(
                name="design_lookup",
                description=(
                    "List research designs (systematic/scoping review, meta-analysis, "
                    "bibliometric, RCT, quasi-experiment, observational, survey, "
                    "diagnostic, prediction model, ML experiment, qualitative, mixed "
                    "methods, case study, design science, R&D, action research, PTK, "
                    "dataset/benchmark, engineering research, methodological and "
                    "position papers) "
                    "with their reporting guideline and checked items; look one up by "
                    "key or alias, or detect it from a manuscript."
                ),
            ),
        ]

    def resources(self) -> list[ResourceSpec]:
        return [
            ResourceSpec(
                uri="paperassist://pack",
                description="Pack plan (requires kind and run_id).",
            ),
            ResourceSpec(
                uri="paperassist://task",
                description="Pack task (requires kind, run_id and task_id).",
            ),
            ResourceSpec(
                uri="paperassist://journal-profiles",
                description="Curated journal format profiles (Indonesia and international).",
            ),
            ResourceSpec(
                uri="paperassist://thesis-profiles",
                description="Curated thesis/dissertation formatting profiles.",
            ),
        ]

    def harness_status(self, workspace: str) -> dict[str, Any]:
        return {"status": "ok", "harness": harness_status(_workspace(workspace))}

    def pack_scaffold(
        self,
        workspace: str,
        kind: str,
        run_id: str | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        root = _workspace(workspace)
        normalized_kind = _kind(kind)
        reject_unknown_keys(payload, _INPUT_KEYS, tool="pack_scaffold")
        inputs = {
            key: value
            for key, value in payload.items()
            if key in _INPUT_KEYS and value not in (None, "", [], ())
        }
        normalized_run_id = run_id or _default_run_id(normalized_kind, inputs)
        with self.workspace_lock(root):
            pack = _BUILDERS[normalized_kind](root, run_id=normalized_run_id, payload=inputs)
        return {
            "status": "ok",
            "executor": "ai-harness",
            "provider_calls": 0,
            "pack": pack.to_dict(),
        }

    def pack_plan(self, workspace: str, kind: str, run_id: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "plan": load_plan(_workspace(workspace), run_id=run_id, kind=_kind(kind)),
        }

    def pack_task(self, workspace: str, kind: str, run_id: str, task_id: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "task": load_task(
                _workspace(workspace),
                run_id=run_id,
                kind=_kind(kind),
                task_id=task_id,
            ),
        }

    def pack_import(
        self,
        workspace: str,
        kind: str,
        run_id: str,
        result_path: str,
    ) -> dict[str, Any]:
        root = _workspace(workspace)
        normalized_kind = _kind(kind)
        with self.workspace_lock(root):
            result = _IMPORTERS[normalized_kind](
                root,
                run_id=run_id,
                result_path=result_path,
            )
        return {"status": "ok", "executor": "ai-harness", "provider_calls": 0, **result}

    def corpus_bind(
        self,
        workspace: str,
        records_path: str | None = None,
        fulltext_root: str | None = None,
        bibliography_path: str | None = None,
        records: list[dict[str, Any]] | None = None,
        emit_bibtex: bool = False,
    ) -> dict[str, Any]:
        root = _workspace(workspace)
        payload: dict[str, Any] = {}
        if records:
            payload["records"] = records
        if records_path:
            payload["records_path"] = records_path
        if fulltext_root:
            payload["fulltext_root"] = fulltext_root
        if bibliography_path:
            payload["bibliography_path"] = bibliography_path
        binding = bind_corpus(root, payload)
        result: dict[str, Any] = {
            "status": "ok",
            "corpus": binding.coverage(),
            "binding": binding.to_dict(),
            "report": format_binding_report(binding),
        }
        if emit_bibtex:
            source_records = list(records or [])
            if not source_records and records_path:
                source_records = list(load_records(payload, root))
            bibtex, warnings = generate_bibtex(binding, source_records)
            result["bibtex"] = bibtex
            result["bibtex_warnings"] = list(warnings)
        return result

    def claim_audit(
        self,
        workspace: str,
        target_path: str,
        locators: list[dict[str, Any]] | None = None,
        records: list[dict[str, Any]] | None = None,
        include_claims: bool = False,
    ) -> dict[str, Any]:
        root = _workspace(workspace)
        text = read_workspace_text(root, target_path, what="manuscript")
        ledger = build_ledger(
            text,
            locators=extract_locators(text) if locators is None else _payload_locators(locators),
            records=list(records or []),
        )
        result: dict[str, Any] = {
            "status": "ok",
            "summary": ledger.summary(),
            "digest": ledger.digest,
            "report": format_ledger_report(ledger),
            "narrative_jsonl": ledger.to_jsonl("narrative"),
            "evidence_jsonl": ledger.to_jsonl("evidence"),
        }
        if include_claims:
            result["ledger"] = ledger.to_dict()
        return result

    def quality_score(
        self,
        workspace: str,
        target_path: str,
        depth_target: int = 500,
        min_anchored: float = 0.6,
        allow_em_dash: bool = False,
        bibliography_path: str | None = None,
        paper_type: str = "auto",
        research_design: str = "auto",
        required_declarations: list[str] | None = None,
        reference_policy: dict[str, Any] | None = None,
        flow_path: str | None = None,
        document_kind: str = "auto",
        thesis_profile: str | None = "auto",
        thesis_stage: str = "auto",
    ) -> dict[str, Any]:
        """``flow_path`` is a JSON file of flow counts: PRISMA for a review,
        CONSORT for a trial or quasi-experiment, STROBE for an observational
        study (whichever the resolved research design uses)."""

        from paperassist.reporting_checks import ReferencePolicy, check_declarations

        root = _workspace(workspace)
        text = read_workspace_text(root, target_path, what="manuscript")
        prisma_flow = participant_flow = None
        if flow_path:
            import json

            from paperassist.participant_flow import check_participant_flow
            from paperassist.reporting_checks import check_prisma_flow, resolve_research_design

            try:
                counts = json.loads(read_workspace_text(root, flow_path, what="flow counts"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"flow counts are not valid JSON: {flow_path}") from exc
            if not isinstance(counts, dict):
                raise ValueError("flow counts must be a JSON object")
            flow_design = resolve_research_design(research_design, text, paper_type=paper_type)
            if flow_design.flow == "prisma":
                prisma_flow = check_prisma_flow([counts])
            elif flow_design.flow in ("consort", "strobe"):
                participant_flow = check_participant_flow(
                    [counts], kind=flow_design.flow, randomised=flow_design.key == "rct"
                )
        entries: list[str] = []
        bib_text: str | None = None
        if bibliography_path:
            bib_text = read_workspace_text(root, bibliography_path, what="bibliography")
            from paperassist.corpus_binder import parse_bib_entries

            entries = [entry.key for entry in parse_bib_entries(bib_text)]
        from paperassist.corpus_binder import parse_bib_entries as _parse
        from paperassist.reporting_checks import (
            audit_references,
            cited_keys,
            resolve_paper_type,
        )

        resolved = resolve_paper_type(paper_type, text)
        reference_audit = None
        if bib_text:
            reference_audit = audit_references(
                _parse(bib_text),
                cited_keys=cited_keys(text),
                policy=ReferencePolicy.from_payload(reference_policy),
            )
        report = score_manuscript(
            text,
            bibliography_entries=entries,
            bibliography_text=bib_text,
            depth_target=depth_target,
            min_anchored=min_anchored,
            allow_em_dash=allow_em_dash,
            paper_type=paper_type,
            research_design=research_design,
            declarations=check_declarations(
                text, required=required_declarations, paper_type=resolved
            ),
            reference_audit=reference_audit,
            prisma_flow=prisma_flow,
            participant_flow=participant_flow,
            asset_root=str((root / target_path).parent),
            document_kind=document_kind,
            thesis_profile=thesis_profile,
            thesis_stage=thesis_stage,
        )
        return {
            "status": "ok",
            "document_kind": report.document_kind,
            "score": round(report.score, 4),
            "grade": report.grade,
            "recommendation": report.recommendation,
            "report": report.to_dict(),
            "markdown": format_quality_report(report),
            "revision_plan": list(revision_plan(report)),
        }

    def research_os(self, workspace: str, **payload: Any) -> dict[str, Any]:
        root = _workspace(workspace)
        reject_unknown_keys(payload, _RESEARCH_KEYS, tool="research_os")
        inputs = {
            key: value
            for key, value in payload.items()
            if key in _RESEARCH_KEYS and value not in (None, "", [], ())
        }
        with self.workspace_lock(root):
            result = run_research_os(root, inputs)
        return {"status": "ok", "executor": "ai-harness", "provider_calls": 0, **result.to_dict()}

    def improvement_verify(
        self,
        workspace: str,
        before_path: str,
        after_path: str,
        depth_target: int = 500,
        max_grounding_drop: float = 0.05,
        max_dimension_drop: float = 0.05,
        allow_em_dash: bool = False,
    ) -> dict[str, Any]:
        root = _workspace(workspace)
        before_text = read_workspace_text(root, before_path, what="baseline")
        after_text = read_workspace_text(root, after_path, what="revision")
        before_ledger = build_ledger(before_text, locators=extract_locators(before_text))
        after_ledger = build_ledger(after_text, locators=extract_locators(after_text))
        before = score_manuscript(
            before_text, ledger=before_ledger, depth_target=depth_target,
            allow_em_dash=allow_em_dash,
        )
        after = score_manuscript(
            after_text, ledger=after_ledger, depth_target=depth_target,
            allow_em_dash=allow_em_dash,
        )
        verdict = verify_revision(
            before,
            after,
            before_ledger=before_ledger,
            after_ledger=after_ledger,
            max_grounding_drop=max_grounding_drop,
            max_dimension_drop=max_dimension_drop,
        )
        return {
            "status": "ok",
            "accepted": verdict.accepted,
            "verdict": verdict.to_dict(),
            "markdown": format_verdict(verdict),
        }

    def journal_lookup(
        self,
        query: str | None = None,
        scope: str | None = None,
        manuscript_path: str | None = None,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        if manuscript_path:
            if not workspace:
                raise ValueError("workspace is required when manuscript_path is given")
            text = read_workspace_text(
                _workspace(workspace), manuscript_path, what="manuscript"
            )
            result = detect_profiles(text)
        elif query:
            result = lookup_profiles(query)
        else:
            items = list_profiles(scope)
            result = {
                "schema": PROFILE_SCHEMA,
                "scope": scope or "all",
                "count": len(items),
                "profiles": items,
            }
        return {
            "status": "ok",
            "provider_calls": 0,
            "result": result,
            "markdown": format_profile_report(result),
        }

    def thesis_lookup(
        self,
        query: str | None = None,
        scope: str | None = None,
        manuscript_path: str | None = None,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        if manuscript_path:
            if not workspace:
                raise ValueError("workspace is required when manuscript_path is given")
            text = read_workspace_text(
                _workspace(workspace), manuscript_path, what="manuscript"
            )
            result = detect_thesis_profiles(text)
        elif query:
            result = lookup_thesis_profiles(query)
        else:
            items = list_thesis_profiles(scope)
            result = {
                "schema": THESIS_PROFILE_SCHEMA,
                "scope": scope or "all",
                "count": len(items),
                "profiles": items,
            }
        return {
            "status": "ok",
            "provider_calls": 0,
            "result": result,
            "markdown": format_thesis_profile_report(result),
        }

    def design_lookup(
        self,
        query: str | None = None,
        category: str | None = None,
        manuscript_path: str | None = None,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        from paperassist.reporting_checks import resolve_paper_type
        from paperassist.research_designs import (
            DESIGNS,
            design_catalogue,
            design_hits,
            design_method_brief,
            explain_detection,
            get_design,
        )

        if manuscript_path:
            if not workspace:
                raise ValueError("workspace is required when manuscript_path is given")
            text = read_workspace_text(_workspace(workspace), manuscript_path, what="manuscript")
            family = resolve_paper_type("auto", text)
            explanation = explain_detection(text, family=family)
            design = get_design(explanation["chosen"])
            result: dict[str, Any] = {
                "detected": design.to_dict(),
                "family": family,
                "confidence": explanation["confidence"],
                "reason": explanation["reason"],
                "candidates": explanation["candidates"],
                "hits": design_hits(text),
            }
            designs = [design]
        elif query:
            design = get_design(query)
            result = {"design": design.to_dict()}
            designs = [design]
        else:
            items = design_catalogue()
            if category:
                items = [item for item in items if item["category"] == category.strip().lower()]
            result = {"count": len(items), "designs": items}
            designs = [DESIGNS[item["key"]] for item in items]
        lines = ["## Research designs", ""]
        if "confidence" in result:
            lines += [
                f"**Detected:** `{result['detected']['key']}` "
                f"(confidence {result['confidence']}: {result['reason']})",
                "",
            ]
            for item in result["candidates"]:
                mark = "" if item["counted"] else f" (below the {item['min_hits']}-mention minimum)"
                lines.append(
                    f"- `{item['key']}`: {item['hits']} mention(s){mark}: "
                    + ", ".join(f"\"{phrase}\"" for phrase in item["matched"])
                )
            lines.append("")
        for design in designs:
            lines += [f"### {design.label} (`{design.key}`)", "", design_method_brief(design), ""]
        return {
            "status": "ok",
            "provider_calls": 0,
            "result": result,
            "markdown": "\n".join(lines),
        }

    def read_resource(
        self,
        resource_uri: str,
        *,
        workspace: str | None = None,
        kind: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        scope: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if resource_uri == "paperassist://journal-profiles":
            items = list_profiles(scope)
            result = {
                "schema": PROFILE_SCHEMA,
                "scope": scope or "all",
                "count": len(items),
                "profiles": items,
            }
            return {
                "status": "ok",
                "result": result,
                "markdown": format_profile_report(result),
            }
        if resource_uri == "paperassist://thesis-profiles":
            items = list_thesis_profiles(scope)
            result = {
                "schema": THESIS_PROFILE_SCHEMA,
                "scope": scope or "all",
                "count": len(items),
                "profiles": items,
            }
            return {
                "status": "ok",
                "result": result,
                "markdown": format_thesis_profile_report(result),
            }
        if workspace is None or kind is None or run_id is None:
            raise ValueError("pack/task resources require workspace, kind, and run_id")
        root = _workspace(workspace)
        normalized_kind = _kind(kind)
        if resource_uri == "paperassist://pack":
            return {"status": "ok", "plan": load_plan(root, run_id=run_id, kind=normalized_kind)}
        if resource_uri == "paperassist://task":
            if not task_id:
                raise ValueError("task resource requires task_id")
            return {
                "status": "ok",
                "task": load_task(
                    root,
                    run_id=run_id,
                    kind=normalized_kind,
                    task_id=task_id,
                ),
            }
        raise ValueError(f"Unsupported resource `{resource_uri}`")


def build_server() -> PaperAssistMcpServer:
    return PaperAssistMcpServer()


__all__ = ["PaperAssistMcpServer", "build_server"]
