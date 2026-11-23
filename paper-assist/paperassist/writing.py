"""Agent-operated LaTeX writing without a PaperAssist-owned language model.

The engine prepares a deterministic writing pack (:mod:`paperassist.writing_pack`)
that an external AI harness executes, then verifies the returned document with
the same safety gates used before. PaperAssist never calls a model provider and
never needs its own API key for the writing stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engine.secret_redaction import contains_secret

from .artifacts import ArtifactRecord, ArtifactStore
from .latex_safety import FORBIDDEN_LATEX as _FORBIDDEN_LATEX
from .path_safety import atomic_write_text, reject_symlink_components
from .protected_blocks import (
    PROTECTED_END,
    PROTECTED_START,
    ProtectedBlockViolation,
    extract_protected_blocks,
    protected_blocks_sha256,
)
from .provenance_audit import (
    ProvenanceReport,
    extract_locators,
    load_locators_payload,
)
from .provenance_audit import (
    audit as audit_provenance,
)
from .references import DEFAULT_REFERENCE_BUDGET_BYTES
from .writing_pack import (
    WRITING_PACK_ROOT,
    WRITING_PLAN_FILENAME,
    WritingPack,
    WritingPackError,
    build_writing_pack,
    pack_directory_name,
    skeleton_document_kind,
)

_FENCE = re.compile(r"\A```(?:latex|tex)?\s*\n(?P<body>.*)\n```\s*\Z", re.DOTALL)
_CITATION = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]+)\}"
)
_BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
_EXPERIMENT_SECTION = re.compile(
    r"\\(?:section|subsection|subsubsection)\*?\s*\{[^{}]*"
    r"(?:experiment|evaluation|result|ablation|benchmark)[^{}]*\}",
    re.IGNORECASE,
)
_QUANTITATIVE_RESULT = re.compile(
    r"(?:\b(?:accuracy|precision|recall|f1|psnr|ssim|bleu|rouge|auc)\b"
    r"[^.\n]{0,80}\d|\d+(?:\.\d+)?\s*\\?%|\b(?:outperform|state-of-the-art)\b)",
    re.IGNORECASE,
)
# Chat-assistant residue and writing-process narration. Disclosure of AI use is
# required by ICMJE/COPE, but it is the authors' statement in the Declarations
# block, never a sentence the harness slips into the argument.
_ASSISTANT_RESIDUE = re.compile(
    r"\bas an ai\b|\bas a(?:n)? (?:large )?language model\b|\bi(?:'m| am) an ai\b|"
    r"\bhere is the (?:revised|updated|requested|rewritten)\b|\bi hope this helps\b|"
    r"\bsebagai (?:sebuah )?(?:model bahasa|asisten ai|kecerdasan buatan)\b|"
    r"\bberikut (?:adalah |ini adalah )?(?:versi|revisi|draf) (?:yang )?(?:telah|sudah)\b|"
    # "Semoga bermanfaat" closes many thesis forewords, so only the chat form.
    r"\bsemoga membantu\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_NON_NUMERIC_COMMANDS = re.compile(
    r"\\(?:cite[a-zA-Z*]*|ref|eqref|autoref|cref|Cref|label|url|href)\s*(?:\[[^\]]*\]\s*)*\{[^{}]*\}"
)
_REF_TARGET = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\s*\{([^{}]*)\}")
_LABEL_TARGET = re.compile(r"\\label\s*\{([^{}]*)\}")
_YEAR = re.compile(r"\b(?:19|20)\d\d\b")


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*$", " ", text, flags=re.M)


def _numbers(text: str) -> set[str]:
    cleaned = _YEAR.sub(" ", _NON_NUMERIC_COMMANDS.sub(" ", text))
    return {number.replace(",", ".") for number in _NUMBER.findall(cleaned)}


def _unsupported_result_sentences(prose: str, protected: str) -> list[str]:
    """Result-like sentences outside the protected block that it does not back.

    A Discussion must be able to restate a result the authors reported. A
    sentence is accepted when every number in it already appears in the
    protected experiment block, or when it states no number and points at a
    table or figure defined there; anything else would be a new result.
    """

    protected_numbers = _numbers(protected)
    protected_labels = set(_LABEL_TARGET.findall(protected))
    offending: list[str] = []
    for sentence in _SENTENCE_BREAK.split(_strip_comments(prose)):
        if not _QUANTITATIVE_RESULT.search(sentence):
            continue
        numbers = _numbers(sentence)
        if numbers:
            if numbers <= protected_numbers:
                continue
        elif set(_REF_TARGET.findall(sentence)) & protected_labels:
            continue
        offending.append(" ".join(sentence.split()))
    return offending


_SAFE_RUN_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
_BRIEF_FIELDS = ("title", "topic", "abstract", "instructions")


class WritingError(RuntimeError):
    pass


class WritingSafetyError(WritingError):
    pass


@dataclass(frozen=True)
class WritingResult:
    artifact: ArtifactRecord
    source_path: str | None
    protected_sha256: str
    request_sha256: str
    response_sha256: str
    writing_mode: str = "agent"
    provenance: ProvenanceReport | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifact"] = self.artifact.to_dict()
        if self.provenance is not None:
            payload["provenance"] = self.provenance.to_dict()
        return payload


def _without_protected_blocks(text: str) -> str:
    pattern = re.compile(
        rf"{re.escape(PROTECTED_START)}.*?{re.escape(PROTECTED_END)}",
        re.DOTALL,
    )
    return pattern.sub("", text)


def _strip_fence(text: str) -> str:
    normalized = text.strip()
    match = _FENCE.fullmatch(normalized)
    return match.group("body").strip() if match is not None else normalized


def _latex_skeleton(title: str, payload: Mapping[str, Any] | None = None) -> str:
    payload = payload or {}
    return skeleton_document_kind(
        title,
        document_kind=str(payload.get("document_kind") or "paper"),
        thesis_type=str(payload.get("thesis_type") or "thesis"),
        research_design=payload.get("research_design"),
        thesis_profile_id=_profile_id(payload.get("thesis_profile")),
        thesis_stage=str(payload.get("thesis_stage") or "final"),
    )


def _profile_id(value: Any) -> str | None:
    """A thesis profile id from a string or a ``{"profile_id": ...}`` mapping."""

    if isinstance(value, Mapping):
        value = value.get("profile_id")
    return str(value).strip() if value else None


class WritingEngine:
    """Deterministic scaffold + fail-closed import for agent-written LaTeX."""

    def __init__(self, workspace: str | Path, *, memory: Any) -> None:
        self.workspace = Path(workspace).expanduser().resolve(strict=True)
        self.memory = memory

    def _workspace_document(self, raw_path: str | Path) -> tuple[Path, str]:
        supplied = Path(raw_path).expanduser()
        lexical = supplied if supplied.is_absolute() else self.workspace / supplied
        lexical = reject_symlink_components(lexical, anchor=self.workspace)
        try:
            relative = lexical.relative_to(self.workspace).as_posix()
        except ValueError as exc:
            raise WritingSafetyError("writing document leaves the workspace") from exc
        if lexical.suffix.lower() != ".tex":
            raise WritingSafetyError("writing target must be a TeX document")
        if lexical.is_symlink() or (lexical.exists() and not lexical.is_file()):
            raise WritingSafetyError("writing target must be a regular file")
        return lexical, relative

    def _source_document(
        self,
        payload: Mapping[str, Any],
        *,
        run_id: str,
    ) -> tuple[Path | None, str, str]:
        raw_source = (
            payload.get("main_tex")
            or payload.get("main_tex_path")
            or payload.get("document_path")
        )
        if raw_source is not None:
            source, relative = self._workspace_document(str(raw_source))
            if not source.is_file():
                raise FileNotFoundError(source)
            return source, relative, source.read_text(encoding="utf-8")
        safe_run_id = _SAFE_RUN_ID.sub("-", run_id).strip(".-_") or "draft"
        relative = f".paperassist/drafts/{safe_run_id}.tex"
        target, relative = self._workspace_document(relative)
        return None, relative, _latex_skeleton(
            str(payload.get("title") or ""), payload
        )

    @staticmethod
    def _brief(payload: Mapping[str, Any]) -> str:
        lines = []
        for field in _BRIEF_FIELDS:
            value = str(payload.get(field) or "").strip()
            if value:
                lines.append(f"{field}: {value}")
        outline = payload.get("outline")
        if isinstance(outline, Sequence) and not isinstance(outline, str | bytes):
            normalized = [str(item).strip() for item in outline if str(item).strip()]
            if normalized:
                lines.append("outline:\n- " + "\n- ".join(normalized))
        return "\n".join(lines)

    def _bibliography_keys(self, payload: Mapping[str, Any]) -> frozenset[str]:
        raw_path = payload.get("bibliography_path") or "references.bib"
        supplied = Path(str(raw_path)).expanduser()
        lexical = supplied if supplied.is_absolute() else self.workspace / supplied
        lexical = reject_symlink_components(lexical, anchor=self.workspace)
        if lexical.is_symlink() or (lexical.exists() and not lexical.is_file()):
            raise WritingSafetyError("bibliography must be a regular file")
        if not lexical.exists():
            return frozenset()
        return frozenset(_BIB_ENTRY.findall(lexical.read_text(encoding="utf-8")))

    @staticmethod
    def _validate_candidate(
        candidate: str,
        *,
        protected_blocks: tuple[str, ...],
        bibliography_keys: frozenset[str],
    ) -> None:
        if len(candidate.encode("utf-8")) > 2 * 1024 * 1024:
            raise WritingSafetyError("generated TeX exceeds the 2 MiB safety limit")
        if contains_secret(candidate):
            raise WritingSafetyError("generated TeX contains secret-like content")
        for required in (
            r"\documentclass",
            r"\begin{document}",
            r"\end{document}",
        ):
            if required not in candidate:
                raise WritingSafetyError(f"generated TeX is missing {required}")
        if _FORBIDDEN_LATEX.search(candidate):
            raise WritingSafetyError("generated TeX contains an unsafe file or shell command")
        try:
            candidate_blocks = extract_protected_blocks(candidate)
        except ProtectedBlockViolation as exc:
            raise WritingSafetyError(str(exc)) from exc
        if candidate_blocks != protected_blocks:
            raise WritingSafetyError("generated TeX changed the protected experiment block")
        prose = _without_protected_blocks(candidate)
        if _EXPERIMENT_SECTION.search(prose):
            raise WritingSafetyError(
                "writing-only output introduced an unprotected experimental section; "
                "Experimental Setup and Results are author-owned and live inside the "
                "protected experiment block"
            )
        invented = _unsupported_result_sentences(prose, "\n".join(protected_blocks))
        if invented:
            raise WritingSafetyError(
                "writing-only output introduced an unprotected experimental claim: "
                + invented[0][:200]
                + " (restate only numbers that appear in the protected block, or "
                "refer to its tables and figures with \\ref)"
            )
        residue = _ASSISTANT_RESIDUE.search(_strip_comments(prose))
        if residue:
            raise WritingSafetyError(
                "draft contains assistant or writing-process narration: "
                f"{residue.group(0)!r}; AI-use disclosure belongs in the author-owned "
                "Declarations block"
            )
        cited = {
            key.strip()
            for group in _CITATION.findall(candidate)
            for key in group.split(",")
            if key.strip()
        }
        unknown = sorted(cited - bibliography_keys)
        if unknown:
            raise WritingSafetyError(
                "generated TeX cites unknown bibliography keys: " + ", ".join(unknown)
            )

    def scaffold(
        self,
        *,
        run_id: str,
        payload: Mapping[str, Any],
        reference_budget_bytes: int = DEFAULT_REFERENCE_BUDGET_BYTES,
    ) -> WritingPack:
        """Build the writing pack the external harness executes."""

        source, relative_path, original = self._source_document(
            payload,
            run_id=run_id,
        )
        brief = self._brief(payload)
        if source is None and not brief:
            raise WritingError("writing request requires a topic, title, abstract, or instructions")
        try:
            protected_blocks = extract_protected_blocks(original)
        except ProtectedBlockViolation as exc:
            raise WritingSafetyError(str(exc)) from exc
        if source is not None and not protected_blocks:
            raise WritingSafetyError(
                "writing-only editing requires a protected experiment block"
            )
        try:
            pack = build_writing_pack(
                self.workspace,
                run_id=run_id,
                payload=payload,
                target_path=relative_path,
                original_text=original,
            )
        except WritingPackError as exc:
            raise WritingError(str(exc)) from exc
        target = self.workspace / relative_path
        if not target.exists():
            atomic_write_text(self.workspace, relative_path, original)
        store = ArtifactStore(
            self.workspace,
            allowed_roots=(pack.directory,),
            allowed_suffixes=(".json", ".md", ".tex"),
            allowed_kinds=("manifest", "report", "latex"),
            memory=self.memory,
        )
        store.register(
            pack.plan_path,
            kind="manifest",
            status="WRITING_PACK_READY",
            media_type="application/json",
            metadata={
                "workflow_id": run_id,
                "writing_mode": "agent",
                "writing_pack_digest": pack.digest,
                "writing_task_count": len(pack.tasks),
                "target_path": relative_path,
            },
        )
        return pack

    def import_draft(
        self,
        *,
        run_id: str,
        payload: Mapping[str, Any],
        draft_text: str | None = None,
        draft_path: str | Path | None = None,
    ) -> WritingResult:
        """Verify a harness-produced document and register it as a draft artifact."""

        source, relative_path, original = self._source_document(
            payload,
            run_id=run_id,
        )
        raw_candidate = draft_text
        candidate_source: str | None = None
        if raw_candidate is None:
            if draft_path is None:
                raise WritingError(
                    "import requires draft_text or draft_path produced by the AI harness"
                )
            candidate_file, candidate_source = self._workspace_document(str(draft_path))
            if not candidate_file.is_file():
                raise FileNotFoundError(candidate_file)
            raw_candidate = candidate_file.read_text(encoding="utf-8")
        try:
            protected_blocks = extract_protected_blocks(original)
        except ProtectedBlockViolation as exc:
            raise WritingSafetyError(str(exc)) from exc
        if not protected_blocks:
            raise WritingSafetyError(
                "writing-only editing requires a protected experiment block"
            )
        bibliography_keys = self._bibliography_keys(payload)
        candidate = _strip_fence(raw_candidate)
        if not candidate.strip():
            raise WritingSafetyError("imported draft is empty")
        self._validate_candidate(
            candidate,
            protected_blocks=protected_blocks,
            bibliography_keys=bibliography_keys,
        )
        provenance = self._audit_provenance(candidate, payload, run_id=run_id)
        if (
            provenance is not None
            and not provenance.passed
            and self._provenance_is_blocking(payload)
        ):
            rendered = "; ".join(provenance.warnings) or "provenance audit failed"
            raise WritingSafetyError("provenance gate refused the draft: " + rendered)
        before_sha256 = protected_blocks_sha256(original)
        atomic_write_text(self.workspace, relative_path, candidate + "\n")
        written = self.workspace / relative_path
        try:
            after_sha256 = protected_blocks_sha256(
                written.read_text(encoding="utf-8")
            )
            if after_sha256 != before_sha256:
                raise WritingSafetyError(
                    "protected experiment hash changed after the write"
                )
            store = ArtifactStore(
                self.workspace,
                allowed_roots=(relative_path,),
                allowed_suffixes=(".tex",),
                allowed_kinds=("latex",),
                memory=self.memory,
            )
            artifact = store.register(
                relative_path,
                kind="latex",
                status="DRAFT_REQUIRES_CLAIM_GATE",
                media_type="application/x-tex",
                metadata={
                    "protected_sha256": after_sha256,
                    "workflow_id": run_id,
                    "source_path": (
                        source.relative_to(self.workspace).as_posix()
                        if source is not None
                        else None
                    ),
                    "draft_source_path": candidate_source,
                    "writing_mode": "agent",
                    "writing_pack_digest": self._pack_digest(
                        str(payload.get("writing_pack_run_id") or run_id)
                    ),
                    "writing_pack_run_id": str(
                        payload.get("writing_pack_run_id") or run_id
                    ),
                    "provider_calls": 0,
                    "provenance_passed": (
                        None if provenance is None else provenance.passed
                    ),
                    "provenance_grounded_ratio": (
                        None if provenance is None else round(provenance.grounded_ratio, 4)
                    ),
                    "provenance_anchorless": (
                        None if provenance is None else len(provenance.anchorless_keys)
                    ),
                },
            )
        except BaseException:
            if source is not None:
                atomic_write_text(self.workspace, relative_path, original)
            else:
                written.unlink(missing_ok=True)
            raise
        return WritingResult(
            artifact=artifact,
            source_path=(
                source.relative_to(self.workspace).as_posix()
                if source is not None
                else None
            ),
            protected_sha256=after_sha256,
            request_sha256=hashlib.sha256(
                (raw_candidate if candidate_source is None else candidate_source).encode("utf-8")
            ).hexdigest(),
            response_sha256=hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
            provenance=provenance,
        )

    def _audit_provenance(
        self, candidate: str, payload: Mapping[str, Any], run_id: str = ""
    ) -> ProvenanceReport | None:
        """Run the deterministic locator/grounding audit when it is requested.

        The audit is opt-in so that existing workspaces keep working unchanged.
        It is enabled by ``provenance: true`` in the import payload, or when the
        pack plan recorded a depth profile that requires provenance tasks.
        """

        mode = payload.get("provenance")
        plan_profile = self._pack_depth_profile(
            str(payload.get("writing_pack_run_id") or payload.get("run_id") or "")
        )
        plan_requires = bool(plan_profile.get("require_provenance_task"))
        enabled = mode is True or str(mode).lower() in {"true", "on", "enforce"}
        if not enabled and not plan_requires:
            return None
        if mode is False or str(mode).lower() in {"false", "off", "skip"}:
            return None

        locators = list(extract_locators(candidate))
        locators.extend(load_locators_payload(payload.get("locators_payload")))
        references_payload = self._load_references_payload(run_id)
        require_locators = bool(payload.get("require_locators", True))
        min_ratio = payload.get("min_grounding_ratio")
        ratio = (
            float(min_ratio)
            if isinstance(min_ratio, (int, float)) and not isinstance(min_ratio, bool)
            else 0.5
        )
        return audit_provenance(
            candidate,
            locators=tuple(locators),
            references_payload=references_payload,
            require_locators=require_locators,
            min_grounding_ratio=ratio,
        )

    def _provenance_is_blocking(self, payload: Mapping[str, Any]) -> bool:
        mode = payload.get("provenance_block", payload.get("provenance"))
        if isinstance(mode, bool):
            return mode
        if str(mode).lower() in {"false", "off", "warn", "skip"}:
            return False
        if str(mode).lower() in {"true", "on", "enforce", "block"}:
            return True
        plan_profile = self._pack_depth_profile(
            str(payload.get("writing_pack_run_id") or payload.get("run_id") or "")
        )
        return bool(plan_profile.get("require_provenance_task"))

    def _pack_depth_profile(self, run_id: str) -> Mapping[str, Any]:
        plan = self._pack_plan(run_id)
        if not isinstance(plan, Mapping):
            return {}
        profile = plan.get("depth_profile")
        return profile if isinstance(profile, Mapping) else {}

    def _pack_plan(self, run_id: str) -> Mapping[str, Any] | None:
        if not run_id:
            return None
        plan = (
            self.workspace
            / WRITING_PACK_ROOT
            / pack_directory_name(run_id)
            / WRITING_PLAN_FILENAME
        )
        if not plan.is_file():
            return None
        try:
            payload = json.loads(plan.read_text(encoding="utf-8"))
        except ValueError:
            return None
        return payload if isinstance(payload, Mapping) else None

    def _load_references_payload(self, run_id: str = "") -> Mapping[str, Any] | None:
        plans: list[Path] = []
        if run_id:
            active = (
                self.workspace
                / WRITING_PACK_ROOT
                / pack_directory_name(run_id)
                / WRITING_PLAN_FILENAME
            )
            if active.is_file():
                plans.append(active)
        plans.extend(
            sorted(
                (
                    self.workspace / WRITING_PACK_ROOT
                ).glob(f"*/{WRITING_PLAN_FILENAME}")
            )
        )
        for pack_plan in plans:
            try:
                plan = json.loads(pack_plan.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(plan, Mapping):
                continue
            candidates: list[Path] = []
            relative = plan.get("references_path")
            if relative:
                candidates.append(self.workspace / str(relative))
            # Excerpts may be regenerated after the pack was built, leaving
            # ``references_path`` unset; the pack directory still holds them.
            candidates.append(pack_plan.parent / "references.json")
            for target in candidates:
                if not target.is_file():
                    continue
                try:
                    payload = json.loads(target.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if isinstance(payload, Mapping):
                    return payload
        return None

    def _pack_digest(self, run_id: str) -> str | None:
        plan = (
            self.workspace
            / WRITING_PACK_ROOT
            / pack_directory_name(run_id)
            / WRITING_PLAN_FILENAME
        )
        if not plan.is_file():
            return None
        try:
            payload = json.loads(plan.read_text(encoding="utf-8"))
        except ValueError:
            return None
        if isinstance(payload, dict) and isinstance(payload.get("digest"), str):
            return str(payload["digest"])
        return None


__all__ = [
    "WritingEngine",
    "WritingError",
    "WritingResult",
    "WritingSafetyError",
    "_strip_fence",
]
