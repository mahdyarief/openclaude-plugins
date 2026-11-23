from __future__ import annotations

import json

import pytest

from paperassist.agent_packs import (
    AgentPackError,
    build_ideation_pack,
    import_ideation,
    load_plan,
    load_task,
)


def _idea(idea_id: str, *, selected: bool) -> dict:
    return {
        "id": idea_id,
        "title": f"Idea {idea_id}",
        "problem": "A concrete problem.",
        "hypothesis": "A testable hypothesis.",
        "approach": "A specific approach.",
        "evaluation_plan": "Measure on a held-out split.",
        "novelty": 3,
        "feasibility": 4,
        "risks": ["data access"],
        "references": [],
        "selected": selected,
    }


@pytest.fixture
def pack(tmp_path):
    return build_ideation_pack(tmp_path, run_id="idea-1", payload={"topic": "Graph retrieval"})


def _write_result(tmp_path, ideas) -> str:
    relative = "ideas-result.json"
    (tmp_path / relative).write_text(
        json.dumps({"topic": "Graph retrieval", "ideas": ideas}), encoding="utf-8"
    )
    return relative


def test_scaffold_writes_plan_and_tasks(tmp_path, pack):
    plan = load_plan(tmp_path, run_id="idea-1", kind="ideation")
    assert plan["executor"] == "ai-harness"
    assert plan["provider_calls"] == 0
    task_ids = [task["task_id"] for task in plan["tasks"]]
    assert task_ids[0] == "literature-scan"
    assert load_task(tmp_path, run_id="idea-1", kind="ideation", task_id=task_ids[0])


def test_import_accepts_exactly_one_selected_idea(tmp_path, pack):
    result_path = _write_result(tmp_path, [_idea("a", selected=True), _idea("b", selected=False)])
    result = import_ideation(tmp_path, run_id="idea-1", result_path=result_path)
    assert result["selected"] == "a"
    assert (tmp_path / result["path"]).is_file()


@pytest.mark.parametrize("flags", [(True, True), (False, False)])
def test_import_rejects_wrong_selection_count(tmp_path, pack, flags):
    ideas = [_idea("a", selected=flags[0]), _idea("b", selected=flags[1])]
    with pytest.raises(AgentPackError, match="exactly one idea"):
        import_ideation(tmp_path, run_id="idea-1", result_path=_write_result(tmp_path, ideas))


def test_import_rejects_out_of_range_rating(tmp_path, pack):
    idea = _idea("a", selected=True)
    idea["novelty"] = 9
    with pytest.raises(AgentPackError):
        import_ideation(tmp_path, run_id="idea-1", result_path=_write_result(tmp_path, [idea]))


@pytest.mark.parametrize("task_id", ["../plan", "..", "a/b", "a\\b", "", ".hidden"])
def test_load_task_rejects_unsafe_ids(tmp_path, pack, task_id):
    with pytest.raises(AgentPackError, match="invalid task_id"):
        load_task(tmp_path, run_id="idea-1", kind="ideation", task_id=task_id)
