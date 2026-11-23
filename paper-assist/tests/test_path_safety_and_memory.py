from __future__ import annotations

import pytest

from paperassist.models import ClaimStatus, ClaimType
from paperassist.path_safety import UnsafePathError, reject_symlink_components
from paperassist.scientific_memory import ScientificMemory


@pytest.mark.parametrize("raw", ["../outside.tex", "sub/../../outside.tex", "sub/.."])
def test_dotdot_segments_cannot_leave_the_anchor(tmp_path, raw):
    workspace = tmp_path / "ws"
    (workspace / "sub").mkdir(parents=True)
    (tmp_path / "outside.tex").write_text("x", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        reject_symlink_components(workspace / raw, anchor=workspace)


def test_contained_paths_are_accepted(tmp_path):
    (tmp_path / "sub").mkdir()
    path = reject_symlink_components(tmp_path / "sub" / "main.tex", anchor=tmp_path)
    assert path.name == "main.tex"


@pytest.fixture
def memory(tmp_path):
    return ScientificMemory(tmp_path / "paperassist.db", trusted_root=tmp_path)


def test_claim_gate_blocks_unsupported_claim(memory):
    memory.add_claim(
        claim_type=ClaimType.EXPERIMENT_RESULT,
        text="Accuracy improves by 4 points.",
        status=ClaimStatus.NEEDS_PRIMARY_SOURCE,
    )
    gate = memory.claim_gate()
    assert gate["passed"] is False
    assert gate["failures"]


def test_claim_gate_rejects_empty_ledger(memory):
    assert memory.claim_gate()["passed"] is False


def test_claim_rejects_secrets(memory):
    with pytest.raises(ValueError, match="credentials"):
        memory.add_claim(
            claim_type=ClaimType.LITERATURE,
            text="token sk-ant-api03-" + "a" * 40,
            status=ClaimStatus.AUTHOR_ASSERTED,
        )
