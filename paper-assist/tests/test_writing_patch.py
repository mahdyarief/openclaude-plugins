from __future__ import annotations

import hashlib

import pytest

from paperassist.path_safety import safe_mkdir
from paperassist.protected_blocks import PROTECTED_END, PROTECTED_START
from paperassist.scientific_memory import ScientificMemory
from paperassist.writing_patch import PatchError, PatchSafetyError, apply_patch

PAPER = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "Intro sentence.\n"
    "Intro sentence twice. Intro sentence twice.\n"
    f"{PROTECTED_START}\n"
    "Accuracy is 91.2\\%.\n"
    f"{PROTECTED_END}\n"
    "\\end{document}\n"
)


@pytest.fixture
def workspace(tmp_path):
    # newline="" keeps LF on Windows so the recorded source hash matches.
    (tmp_path / "main.tex").write_text(PAPER, encoding="utf-8", newline="")
    return tmp_path


def _patch(workspace, **overrides):
    state = safe_mkdir(workspace / ".paperassist", anchor=workspace)
    arguments = {
        "memory": ScientificMemory(state / "paperassist.db", trusted_root=workspace),
        "run_id": "patch-1",
        "target": "main.tex",
        "source_sha256": hashlib.sha256(PAPER.encode("utf-8")).hexdigest(),
        "anchor": "Intro sentence.\n",
        "replacement": "A sharper opening sentence.\n",
    }
    arguments.update(overrides)
    return apply_patch(workspace, **arguments)


def test_patch_applies_and_preserves_protected_block(workspace):
    result = _patch(workspace)
    text = (workspace / "main.tex").read_text(encoding="utf-8")
    assert "A sharper opening sentence." in text
    assert "Accuracy is 91.2" in text
    assert result.to_dict()["code"] == "PATCH_APPLIED"


def test_stale_source_hash_is_refused(workspace):
    with pytest.raises(PatchSafetyError, match="source changed"):
        _patch(workspace, source_sha256="0" * 64)


def test_ambiguous_anchor_is_refused(workspace):
    with pytest.raises(PatchSafetyError, match="not unique"):
        _patch(workspace, anchor="Intro sentence twice.")


def test_missing_anchor_is_reported(workspace):
    with pytest.raises(PatchError, match="not found"):
        _patch(workspace, anchor="No such text")


def test_protected_block_cannot_be_edited(workspace):
    with pytest.raises(PatchSafetyError, match="protected"):
        _patch(workspace, anchor="Accuracy is 91.2\\%.", replacement="Accuracy is 99.9\\%.")
    assert (workspace / "main.tex").read_bytes().decode("utf-8") == PAPER


def test_unsafe_latex_is_refused(workspace):
    with pytest.raises(PatchSafetyError, match="unsafe"):
        _patch(workspace, replacement="\\input{/etc/passwd}\n")


def test_target_outside_workspace_is_refused(workspace):
    # The file exists, so only the containment check can stop the write.
    outside = workspace.parent / "other.tex"
    outside.write_text(PAPER, encoding="utf-8", newline="")
    with pytest.raises(PatchSafetyError, match="leaves workspace"):
        _patch(workspace, target="../other.tex")
    assert outside.read_text(encoding="utf-8") == PAPER
