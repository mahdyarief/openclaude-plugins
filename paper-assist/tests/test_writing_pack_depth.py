"""Tests for depth policy, context-aware tasks, and pack integration."""

from __future__ import annotations

import json

import pytest

from paperassist.context_inventory import ContextSafetyError, inventory_from_payload
from paperassist.writing_pack import (
    DEFAULT_DEPTH,
    DEPTH_PROFILES,
    THESIS_BARE_SECTIONS,
    build_tasks,
    build_writing_pack,
    skeleton_document_kind,
)

MAIN_TEX = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "% PAPERASSIST-PROTECTED-EXPERIMENT-START\n"
    "\\section{Results}\n"
    "A measured value is reported here.\n"
    "% PAPERASSIST-PROTECTED-EXPERIMENT-END\n"
    "\\section{Introduction}\n"
    "Prior work exists \\cite{k1}.\n"
    "\\end{document}\n"
)

BIB = "@article{k1,\n author={A.},\n title={T},\n year={2020}\n}\n"


def make_workspace(root):
    (root / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
    (root / "refs.bib").write_text(BIB, encoding="utf-8")
    (root / "rows.json").write_text(
        json.dumps([{"id": 1, "value": 0.5}, {"id": 2, "value": 0.7}]),
        encoding="utf-8",
    )
    (root / "notes.md").write_text("# Context\n\nSome material.\n", encoding="utf-8")


def task_ids(tasks):
    return [task.task_id for task in tasks]


def test_depth_profiles_are_ordered():
    shallow = DEPTH_PROFILES["shallow"]
    standard = DEPTH_PROFILES["standard"]
    deep = DEPTH_PROFILES["deep"]
    assert (
        shallow["min_words_per_section"]
        < standard["min_words_per_section"]
        < deep["min_words_per_section"]
    )
    assert shallow["require_evidence_tasks"] is False
    assert deep["require_evidence_tasks"] is True


def test_default_depth_is_standard():
    tasks = build_tasks(
        {}, target="main.tex", allowed_keys=("k1",), reference_count=1
    )
    assert tasks
    assert DEFAULT_DEPTH == "standard"


def test_invalid_depth_falls_back_to_standard():
    tasks = build_tasks(
        {"depth": "nonsense", "phases": ["init", "provenance"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
    )
    assert "provenance-locators" in task_ids(tasks)


def test_deep_depth_adds_evidence_and_provenance_tasks(tmp_path):
    make_workspace(tmp_path)
    inventory = inventory_from_payload(
        tmp_path, {"context_paths": ["rows.json", "notes.md"]}
    )
    tasks = build_tasks(
        {"depth": "deep", "phases": ["init", "evidence", "provenance"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
        context=inventory,
    )
    ids = task_ids(tasks)
    assert "evidence-reconciliation" in ids
    assert "provenance-locators" in ids
    evidence = next(task for task in tasks if task.task_id == "evidence-reconciliation")
    assert "records" in evidence.instructions
    assert "denominator" in evidence.instructions


def test_shallow_depth_skips_evidence_and_provenance(tmp_path):
    make_workspace(tmp_path)
    inventory = inventory_from_payload(tmp_path, {"context_paths": ["rows.json"]})
    tasks = build_tasks(
        {"depth": "shallow", "phases": ["init", "evidence", "provenance"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
        context=inventory,
    )
    ids = task_ids(tasks)
    assert "evidence-reconciliation" not in ids
    assert "provenance-locators" not in ids


def test_evidence_task_requires_data_sources(tmp_path):
    make_workspace(tmp_path)
    inventory = inventory_from_payload(tmp_path, {"context_paths": ["notes.md"]})
    tasks = build_tasks(
        {"depth": "deep", "phases": ["evidence"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
        context=inventory,
    )
    assert "evidence-reconciliation" not in task_ids(tasks)


def test_section_instructions_include_depth_target(tmp_path):
    make_workspace(tmp_path)
    inventory = inventory_from_payload(
        tmp_path, {"context_paths": ["rows.json", "notes.md"]}
    )
    tasks = build_tasks(
        {"depth": "deep", "phases": ["init"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
        context=inventory,
    )
    intro = next(task for task in tasks if task.section == "Introduction")
    assert "at least 900 words" in intro.instructions
    assert "tabular source" in intro.instructions
    assert "UNTRUSTED" in intro.instructions


def test_em_dash_is_banned_in_generated_instructions():
    tasks = build_tasks(
        {"phases": ["init"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
    )
    assert tasks
    for task in tasks:
        assert "never use an em dash" in task.instructions


def test_em_dash_can_be_allowed_explicitly():
    tasks = build_tasks(
        {"phases": ["init"], "allow_em_dash": True},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
    )
    assert tasks
    for task in tasks:
        assert "never use an em dash" not in task.instructions


def test_pack_writes_context_artifacts(tmp_path):
    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="run-1",
        payload={
            "depth": "deep",
            "context_paths": ["rows.json", "notes.md"],
            "phases": ["init", "evidence", "provenance"],
        },
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    data = pack.to_dict()
    assert data["depth"] == "deep"
    assert data["context_path"] is not None
    assert data["context_brief_path"] is not None
    assert data["context_signals"]["data_sources"] == 1
    assert data["depth_profile"]["require_evidence_tasks"] is True
    assert (tmp_path / data["context_path"]).is_file()
    assert "UNTRUSTED" in (tmp_path / data["context_brief_path"]).read_text(
        encoding="utf-8"
    )


def test_pack_without_context_has_no_context_artifacts(tmp_path):
    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="run-2",
        payload={"depth": "standard", "phases": ["init"]},
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    data = pack.to_dict()
    assert data["context_path"] is None
    assert data["context_brief_path"] is None
    assert data["context_signals"] == {}


def test_plan_records_depth_profile(tmp_path):
    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="run-3",
        payload={"depth": "shallow", "phases": ["init"]},
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    plan = json.loads((tmp_path / pack.plan_path).read_text(encoding="utf-8"))
    assert plan["depth"] == "shallow"
    assert plan["depth_profile"]["min_words_per_section"] == 250


def test_min_words_override(tmp_path):
    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="run-4",
        payload={
            "depth": "standard",
            "min_words_per_section": 1200,
            "phases": ["init"],
        },
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    assert pack.to_dict()["depth_profile"]["min_words_per_section"] == 1200


def test_thesis_mode_uses_generic_thesis_chapters():
    tasks = build_tasks(
        {"document_kind": "thesis", "phases": ["init"]},
        target="main.tex",
        allowed_keys=("k1",),
        reference_count=1,
    )
    ids = task_ids(tasks)
    assert "section-pendahuluan" in ids
    assert "section-tinjauan-pustaka" in ids
    assert "section-metodologi-penelitian" in ids
    assert "section-hasil-dan-pembahasan" in ids
    assert "section-kesimpulan-dan-saran" in ids
    assert "section-introduction" not in ids


def test_thesis_mode_can_be_overridden_with_custom_sections():
    tasks = build_tasks(
        {
            "document_kind": "thesis",
            "sections": ["Latar Belakang", "Analisis Sistem"],
            "phases": ["init"],
        },
        target="main.tex",
        allowed_keys=(),
        reference_count=0,
    )
    ids = task_ids(tasks)
    assert "section-latar-belakang" in ids
    assert "section-analisis-sistem" in ids
    assert "section-pendahuluan" not in ids


def test_thesis_refine_uses_thesis_chapters():
    tasks = build_tasks(
        {"document_kind": "thesis", "phases": ["refine"]},
        target="main.tex",
        allowed_keys=(),
        reference_count=0,
    )
    ids = task_ids(tasks)
    assert "refine-pendahuluan" in ids
    assert "refine-tinjauan-pustaka" in ids
    assert "refine-introduction" not in ids


def test_thesis_skeleton_is_generic_chapter_scaffold():
    skeleton = skeleton_document_kind(
        "Judul Uji", document_kind="thesis", thesis_type="tesis"
    )
    assert "\\documentclass[12pt]{report}" in skeleton
    assert "\\tableofcontents" in skeleton
    for chapter in THESIS_BARE_SECTIONS:
        assert f"\\chapter{{{chapter}}}" in skeleton
    assert "\\section{Introduction}" not in skeleton
    assert "Telkom" not in skeleton
    assert "MCP" not in skeleton


def test_paper_mode_is_unchanged():
    skeleton = skeleton_document_kind("Judul Uji", document_kind="paper")
    assert "\\documentclass{article}" in skeleton
    assert "\\section{Introduction}" in skeleton
    assert "\\chapter{" not in skeleton


def test_thesis_profile_defaults_and_override(tmp_path):
    make_workspace(tmp_path)
    default_pack = build_writing_pack(
        tmp_path,
        run_id="run-t1",
        payload={"document_kind": "thesis", "phases": ["init"]},
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    profile = default_pack.to_dict()["thesis_profile"]
    assert profile["documentclass"] == "report"
    assert profile["front_matter"]["table_of_contents"] is True

    custom_pack = build_writing_pack(
        tmp_path,
        run_id="run-t2",
        payload={
            "document_kind": "thesis",
            "thesis_profile": {
                "documentclass": "book",
                "language": "english",
                "front_matter": {"list_of_figures": False},
            },
            "phases": ["init"],
        },
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    custom = custom_pack.to_dict()["thesis_profile"]
    assert custom["documentclass"] == "book"
    assert custom["language"] == "english"
    assert custom["front_matter"]["list_of_figures"] is False
    assert custom["front_matter"]["table_of_contents"] is True


def test_paper_pack_reports_paper_kind(tmp_path):
    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="run-p1",
        payload={"phases": ["init"]},
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    assert pack.to_dict()["document_kind"] == "paper"


def test_context_paths_must_stay_in_workspace(tmp_path):
    make_workspace(tmp_path)
    outside = tmp_path.parent / "leak.md"
    outside.write_text("secret\n", encoding="utf-8")
    with pytest.raises(ContextSafetyError):
        build_writing_pack(
            tmp_path,
            run_id="run-5",
            payload={"context_paths": [str(outside)]},
            target_path="main.tex",
            original_text=MAIN_TEX,
        )
