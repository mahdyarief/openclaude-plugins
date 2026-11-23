from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engine.secret_redaction import contains_secret

from .artifacts import ArtifactRecord, ArtifactStore
from .latex_safety import FORBIDDEN_LATEX as _FORBIDDEN_LATEX
from .path_safety import atomic_write_text, reject_symlink_components
from .protected_blocks import (
    ProtectedBlockViolation,
    extract_protected_blocks,
    protected_blocks_sha256,
)
from .writing import _strip_fence


class PatchError(RuntimeError):
    pass


class PatchSafetyError(PatchError):
    pass


class UnsupportedMultiFileEdit(PatchError):
    """Single-file v1 cannot perform cross-file refactors."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "UNSUPPORTED_MULTI_FILE_EDIT: single patch edits one target .tex only; "
            "specify a single target file. " + detail
        )
        self.code = "UNSUPPORTED_MULTI_FILE_EDIT"


@dataclass(frozen=True)
class PatchResult:
    artifact: ArtifactRecord
    target_path: str
    source_sha256: str
    protected_sha256: str
    request_sha256: str
    response_sha256: str
    anchor: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifact"] = self.artifact.to_dict()
        payload["code"] = "PATCH_APPLIED"
        return payload


def _looks_truncated(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return True
    # Trailing escape or unclosed group/env strongly suggests cut-off output.
    if stripped.endswith("\\"):
        return True
    if stripped.count("{") != stripped.count("}"):
        return True
    begins = len(re.findall(r"\\begin\{", stripped))
    ends = len(re.findall(r"\\end\{", stripped))
    if begins != ends:
        return True
    # Model fence leftovers or ellipsis markers are not valid patches.
    return bool(stripped.endswith("```"))


def _resolve_target(workspace: Path, raw: str | Path) -> tuple[Path, str]:
    supplied = Path(raw).expanduser()
    lexical = supplied if supplied.is_absolute() else workspace / supplied
    try:
        lexical = reject_symlink_components(lexical, anchor=workspace)
    except ValueError as exc:
        raise PatchSafetyError(f"patch target leaves workspace: {raw!r}") from exc
    try:
        relative = lexical.relative_to(workspace).as_posix()
    except ValueError as exc:
        raise PatchSafetyError(f"patch target leaves workspace: {raw!r}") from exc
    if Path(relative).suffix.lower() != ".tex":
        raise PatchSafetyError("patch target must be a single .tex file")
    if lexical.is_symlink() or (lexical.exists() and not lexical.is_file()):
        raise PatchSafetyError("patch target must be a regular file")
    if not lexical.is_file():
        raise FileNotFoundError(lexical)
    return lexical, relative


def apply_patch(
    workspace: str | Path,
    *,
    memory: Any,
    run_id: str,
    target: str | Path,
    source_sha256: str,
    anchor: str,
    replacement: str,
    instructions: str = "",
    allow_line_range: tuple[int, int] | None = None,
    extra_targets: list[str] | None = None,
) -> PatchResult:
    """Apply an agent-supplied replacement for one unique anchor.

    The replacement text comes from the external AI harness; PaperAssist only
    validates and commits it. Every safety check fails closed.
    """
    if extra_targets:
        raise UnsupportedMultiFileEdit(f"received {len(extra_targets) + 1} targets")
    root = Path(workspace).expanduser().resolve(strict=True)
    target_path, relative = _resolve_target(root, target)
    original = target_path.read_bytes().decode("utf-8")
    actual_sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if actual_sha != source_sha256:
        raise PatchSafetyError(
            "source changed since source_sha was recorded; refusing patch "
            "(concurrent modification)"
        )
    normalized_anchor = str(anchor or "")
    if not normalized_anchor.strip():
        raise PatchError("patch anchor must be non-empty")
    occurrences = original.count(normalized_anchor)
    if occurrences == 0:
        raise PatchError("patch anchor not found in target")
    if occurrences > 1:
        raise PatchSafetyError("patch anchor is not unique; refusing patch")
    if allow_line_range is not None:
        start, end = allow_line_range
        if start < 1 or end < start:
            raise PatchError("invalid allow_line_range")
        lines = original.splitlines()
        anchor_line = next(
            (i + 1 for i, line in enumerate(lines) if normalized_anchor in line),
            None,
        )
        # Anchor may span lines; fall back to substring search for range check.
        if anchor_line is None:
            offset = original.index(normalized_anchor)
            anchor_line = original[:offset].count("\n") + 1
        if not (start <= anchor_line <= end):
            raise PatchSafetyError("patch anchor outside allowed range")
    try:
        protected_before = extract_protected_blocks(original)
    except ProtectedBlockViolation as exc:
        raise PatchSafetyError(str(exc)) from exc
    if not protected_before:
        raise PatchSafetyError("patch requires a protected experiment block")

    # v1 scope: never auto-expand or flatten \\input/\\include.
    # Editing the single target file itself is allowed, but cross-file
    # refactors are explicitly unsupported.
    replacement_text = _strip_fence(str(replacement or "")).strip("\n")
    if not replacement_text:
        raise PatchSafetyError("patch replacement is empty; refusing to write")
    if _looks_truncated(replacement_text):
        raise PatchSafetyError("patch replacement looks truncated; refusing to write")
    replacement = replacement_text
    if contains_secret(replacement):
        raise PatchSafetyError("patch output contains secret-like content")
    if _FORBIDDEN_LATEX.search(replacement):
        raise PatchSafetyError("patch output contains unsafe file or shell command")
    if normalized_anchor not in original:
        raise PatchSafetyError("anchor vanished before apply; refusing patch")
    # Enforce scope: replacement must not introduce protected-marker changes
    # beyond byte preservation; full-document check happens after splice.
    candidate = original.replace(normalized_anchor, replacement, 1)
    if _looks_truncated(candidate):
        raise PatchSafetyError("patched document looks structurally incomplete")
    for required in (r"\documentclass", r"\begin{document}", r"\end{document}"):
        if required not in candidate:
            raise PatchSafetyError(f"patched document is missing {required}")
    try:
        candidate_blocks = extract_protected_blocks(candidate)
    except ProtectedBlockViolation as exc:
        raise PatchSafetyError(str(exc)) from exc
    if candidate_blocks != protected_before:
        raise PatchSafetyError("patch changed the protected experiment block")
    before_hash = protected_blocks_sha256(original)
    atomic_write_text(root, relative, candidate if candidate.endswith("\n") else candidate + "\n")
    written = root / relative
    try:
        after_hash = protected_blocks_sha256(written.read_bytes().decode("utf-8"))
        if after_hash != before_hash:
            raise PatchSafetyError("protected hash changed after patch")
        store = ArtifactStore(
            root,
            allowed_roots=(relative,),
            allowed_suffixes=(".tex",),
            allowed_kinds=("latex",),
            memory=memory,
        )
        artifact = store.register(
            relative,
            kind="latex",
            status="DRAFT_REQUIRES_CLAIM_GATE",
            media_type="application/x-tex",
            metadata={
                "protected_sha256": after_hash,
                "workflow_id": run_id,
                "source_path": relative,
                "patch_anchor": normalized_anchor[:512],
                "patch_source_sha256": source_sha256,
                "patch_allow_range": list(allow_line_range) if allow_line_range else None,
                "patch_instructions": str(instructions or "")[:512],
                "writing_mode": "agent",
                "provider_calls": 0,
            },
        )
    except BaseException:
        atomic_write_text(root, relative, original)
        raise
    return PatchResult(
        artifact=artifact,
        target_path=relative,
        source_sha256=source_sha256,
        protected_sha256=after_hash,
        request_sha256=hashlib.sha256(
            f"{source_sha256}\x1f{normalized_anchor}".encode()
        ).hexdigest(),
        response_sha256=hashlib.sha256(replacement.encode("utf-8")).hexdigest(),
        anchor=normalized_anchor[:512],
    )


__all__ = [
    "PatchError",
    "PatchResult",
    "PatchSafetyError",
    "UnsupportedMultiFileEdit",
    "apply_patch",
]
