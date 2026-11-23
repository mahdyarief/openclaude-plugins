"""Agent-executable packs for ideation, review and experiments.

PaperAssist owns no language model. Every capability that used to call an
OpenAI-compatible provider now becomes a deterministic *task pack*:

* PaperAssist writes the plan, the task files, the brief and an editable
  target document.
* The AI harness (OpenClaude, Claude Code, Freebuff, a human) performs the
  tasks and returns a JSON/LaTeX result.
* PaperAssist validates the result and records it. No network model call is
  ever made here.

The three packs share one envelope (``plan.json`` + ``tasks/*.json`` +
``agent-brief.md`` + a payload file) so an MCP client can drive all of them
the same way.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.secret_redaction import contains_secret

from .artifacts import sha256_file
from .path_safety import atomic_write_text, reject_symlink_components, safe_mkdir

PACK_SCHEMA = "paperassist.agent-pack/v1"
TASK_SCHEMA = "paperassist.agent-task/v1"
PACK_ROOT = ".paperassist/packs"
PLAN_FILENAME = "plan.json"
BRIEF_FILENAME = "agent-brief.md"
TASKS_DIRNAME = "tasks"

IDEA_SCHEMA = "paperassist.ideation-result/v1"
REVIEW_SCHEMA = "paperassist.review-result/v1"
EXPERIMENT_SCHEMA = "paperassist.experiment-result/v1"

IDEAS_FILENAME = "ideas.json"
REVIEW_FILENAME = "review.json"
EXPERIMENT_FILENAME = "experiment.json"

KIND_IDEATION = "ideation"
KIND_REVIEW = "review"
KIND_EXPERIMENT = "experiment"

REVIEW_DECISIONS = frozenset({"Accept", "Reject"})
REVIEW_RATINGS_1_4 = (
    "Originality",
    "Quality",
    "Clarity",
    "Significance",
    "Soundness",
    "Presentation",
    "Contribution",
)
EXPERIMENT_STATUSES = frozenset({"COMPLETED", "FAILED", "BLOCKED"})


class AgentPackError(RuntimeError):
    """Raised when a pack cannot be built or an imported result is invalid."""


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    phase: str
    title: str
    skill: str
    instructions: str
    target: str
    acceptance: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    inputs: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TASK_SCHEMA,
            "task_id": self.task_id,
            "phase": self.phase,
            "title": self.title,
            "skill": self.skill,
            "target": self.target,
            "instructions": self.instructions.strip() + "\n",
            "acceptance": list(self.acceptance),
            "depends_on": list(self.depends_on),
            "inputs": dict(self.inputs),
        }


@dataclass(frozen=True)
class AgentPack:
    run_id: str
    kind: str
    directory: str
    plan_path: str
    brief_path: str
    target_path: str
    digest: str
    tasks: tuple[AgentTask, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "kind": self.kind,
            "directory": self.directory,
            "plan_path": self.plan_path,
            "brief_path": self.brief_path,
            "target_path": self.target_path,
            "digest": self.digest,
            "task_count": len(self.tasks),
            "provider_calls": 0,
            "executor": "ai-harness",
            "tasks": [task.to_dict() for task in self.tasks],
            "next_command": _next_command(self.kind, self.run_id, self.target_path),
        }


def _next_command(kind: str, run_id: str, target: str) -> str:
    verb = {
        KIND_IDEATION: "ideate",
        KIND_REVIEW: "review",
        KIND_EXPERIMENT: "experiment",
    }[kind]
    return f"paperassist {verb} --workspace <workspace> --run-id {run_id} --import {target}"


def pack_slug(value: object) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or "untitled"


def pack_directory(kind: str, run_id: str) -> str:
    return f"{PACK_ROOT}/{kind}/{pack_slug(run_id)}"


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _relative(workspace: Path, raw: str | Path, *, what: str) -> tuple[Path, str]:
    supplied = Path(raw).expanduser()
    lexical = supplied if supplied.is_absolute() else workspace / supplied
    try:
        lexical = reject_symlink_components(lexical, anchor=workspace)
    except ValueError as exc:
        raise AgentPackError(f"{what} leaves the workspace") from exc
    try:
        relative = lexical.relative_to(workspace).as_posix()
    except ValueError as exc:
        raise AgentPackError(f"{what} leaves the workspace") from exc
    return lexical, relative


def _task_acceptance(kind: str) -> tuple[str, ...]:
    common = (
        "The result file is valid JSON with the documented schema.",
        "No secret, credential, or provider key is written into the result.",
    )
    if kind == KIND_IDEATION:
        return common + (
            "Every idea states a falsifiable hypothesis and an evaluation plan.",
            "Every cited key exists in the workspace bibliography.",
        )
    if kind == KIND_REVIEW:
        return common + (
            "Every score stays inside its declared range.",
            "Every weakness is actionable and tied to the manuscript.",
            "The decision is exactly Accept or Reject.",
        )
    return common + (
        "Every metric is produced by a command that actually ran.",
        "Every artifact path exists and its sha256 matches the recorded hash.",
        "No result is invented or copied from another run.",
    )


def _write_pack(
    workspace: Path,
    *,
    run_id: str,
    kind: str,
    payload: Mapping[str, Any],
    tasks: Sequence[AgentTask],
    target_name: str,
    target_text: str,
    title: str,
    extra: Mapping[str, Any] | None = None,
) -> AgentPack:
    directory = pack_directory(kind, run_id)
    safe_mkdir(workspace / directory, anchor=workspace)
    plan_path = f"{directory}/{PLAN_FILENAME}"
    brief_path = f"{directory}/{BRIEF_FILENAME}"
    target_path = f"{directory}/{target_name}"
    core: dict[str, Any] = {
        "schema": PACK_SCHEMA,
        "run_id": run_id,
        "kind": kind,
        "title": title,
        "inputs": dict(payload),
        "target_path": target_path,
        "acceptance": list(_task_acceptance(kind)),
        "executor": "ai-harness",
        "provider_calls": 0,
        "tasks": [task.to_dict() for task in tasks],
        **dict(extra or {}),
    }
    digest = hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()
    plan = {**core, "digest": digest}
    for task in tasks:
        atomic_write_text(
            workspace,
            f"{directory}/{TASKS_DIRNAME}/{task.task_id}.json",
            json.dumps(task.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    atomic_write_text(workspace, target_path, target_text)
    atomic_write_text(workspace, plan_path, json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_write_text(workspace, brief_path, _brief(plan))
    return AgentPack(
        run_id=run_id,
        kind=kind,
        directory=directory,
        plan_path=plan_path,
        brief_path=brief_path,
        target_path=target_path,
        digest=digest,
        tasks=tuple(tasks),
    )


def _brief(plan: Mapping[str, Any]) -> str:
    lines = [
        f"# {str(plan['kind']).capitalize()} brief — {plan.get('title') or plan['run_id']}",
        "",
        "PaperAssist owns no language model. You are the executor: perform each",
        "task below, edit the target file, then import it for validation.",
        "",
        "## Scope",
        "",
        f"- Target: `{plan['target_path']}`",
        f"- Tasks: {len(plan['tasks'])}",
        "",
        "## Acceptance (enforced on import)",
        "",
    ]
    lines.extend(f"- {rule}" for rule in plan["acceptance"])
    lines.extend(["", "## Tasks", ""])
    for index, task in enumerate(plan["tasks"], start=1):
        lines.append(f"{index}. `{task['task_id']}` — {task['title']}")
    lines.extend(
        [
            "",
            "## Import",
            "",
            "```bash",
            _next_command(str(plan["kind"]), str(plan["run_id"]), str(plan["target_path"])),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def load_plan(workspace: str | Path, *, run_id: str, kind: str) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve(strict=True)
    path = root / pack_directory(kind, run_id) / PLAN_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"{kind} pack not found for run {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AgentPackError("pack plan is not a JSON object")
    return payload


_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _check_task_id(task_id: str) -> str:
    """Task ids are file stems; refuse separators and ``..`` before any read."""

    value = str(task_id or "")
    if not _TASK_ID.fullmatch(value) or ".." in value:
        raise AgentPackError(f"invalid task_id: {task_id!r}")
    return value


def load_task(workspace: str | Path, *, run_id: str, kind: str, task_id: str) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve(strict=True)
    task_id = _check_task_id(task_id)
    path = root / pack_directory(kind, run_id) / TASKS_DIRNAME / f"{task_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"{kind} task not found: {task_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AgentPackError("task file is not a JSON object")
    return payload


# --------------------------------------------------------------------------
# Ideation
# --------------------------------------------------------------------------


def build_ideation_pack(
    workspace: str | Path,
    *,
    run_id: str,
    payload: Mapping[str, Any],
) -> AgentPack:
    root = Path(workspace).expanduser().resolve(strict=True)
    topic = _require_text(payload.get("topic"), "topic")
    num_ideas = _positive_int(payload.get("num_ideas"), default=5)
    venue = str(payload.get("venue") or "").strip()
    constraints = str(payload.get("constraints") or "").strip()
    allowed_keys = _bibliography_keys(root, payload)
    template = {
        "schema": IDEA_SCHEMA,
        "topic": topic,
        "venue": venue,
        "ideas": [],
        "notes": "Fill `ideas` with the harness-produced idea cards.",
    }
    tasks = [
        AgentTask(
            task_id="literature-scan",
            phase="discover",
            title="Map the closest prior work",
            skill="literature-review",
            target=f"{pack_directory(KIND_IDEATION, run_id)}/literature.md",
            instructions=(
                "Search the literature for the closest prior work on the topic. Record "
                "each key paper with its claim, method, and gap. Use the literature and "
                "bibliography MCP tools; do not invent citations."
            ),
        ),
        AgentTask(
            task_id="idea-cards",
            phase="generate",
            title=f"Draft {num_ideas} idea cards",
            skill="ideation",
            target=f"{pack_directory(KIND_IDEATION, run_id)}/{IDEAS_FILENAME}",
            inputs={"num_ideas": num_ideas, "constraints": constraints},
            instructions=(
                f"Write {num_ideas} distinct research ideas for the topic. Each idea "
                "must contain a falsifiable hypothesis, the smallest decisive "
                "experiment, expected evidence, risks, and an evaluation plan. "
                "Avoid incremental variants of the same idea."
            ),
            depends_on=("literature-scan",),
        ),
        AgentTask(
            task_id="novelty-check",
            phase="critique",
            title="Check novelty and feasibility",
            skill="ideation-critique",
            target=f"{pack_directory(KIND_IDEATION, run_id)}/{IDEAS_FILENAME}",
            instructions=(
                "For every idea, compare against the literature scan, mark "
                "`novelty` and `feasibility` (1-5), and list the strongest "
                "objection. Drop or merge duplicates."
            ),
            depends_on=("idea-cards",),
        ),
        AgentTask(
            task_id="rank-and-select",
            phase="select",
            title="Rank ideas and select the next experiment",
            skill="ideation-critique",
            target=f"{pack_directory(KIND_IDEATION, run_id)}/{IDEAS_FILENAME}",
            instructions=(
                "Sort ideas by expected contribution per unit of compute, then set "
                "`selected` on exactly one idea. Explain the choice in `notes`."
            ),
            depends_on=("novelty-check",),
        ),
    ]
    return _write_pack(
        root,
        run_id=run_id,
        kind=KIND_IDEATION,
        payload=payload,
        tasks=tasks,
        target_name=IDEAS_FILENAME,
        target_text=json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        title=topic,
        extra={"allowed_citation_keys": list(allowed_keys)},
    )


def import_ideation(
    workspace: str | Path,
    *,
    run_id: str,
    result_path: str | Path,
) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve(strict=True)
    plan = load_plan(root, run_id=run_id, kind=KIND_IDEATION)
    payload = _read_result(root, result_path, what="ideation result")
    _reject_secrets(payload)
    topic = str(payload.get("topic") or plan.get("title") or "").strip()
    if not topic:
        raise AgentPackError("ideation result must carry a topic")
    raw_ideas = payload.get("ideas")
    if not isinstance(raw_ideas, list) or not raw_ideas:
        raise AgentPackError("ideation result must contain a non-empty `ideas` list")
    allowed = set(plan.get("allowed_citation_keys") or ())
    ideas: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_ideas, start=1):
        if not isinstance(raw, Mapping):
            raise AgentPackError(f"idea {index} is not a JSON object")
        idea_id = pack_slug(raw.get("id") or raw.get("title"))
        if idea_id in seen:
            raise AgentPackError(f"duplicate idea id: {idea_id}")
        seen.add(idea_id)
        card: dict[str, Any] = {
            "id": idea_id,
            "title": _require_text(raw.get("title"), f"idea {index} title"),
            "problem": _require_text(raw.get("problem"), f"idea {index} problem"),
            "hypothesis": _require_text(raw.get("hypothesis"), f"idea {index} hypothesis"),
            "approach": _require_text(raw.get("approach"), f"idea {index} approach"),
            "evaluation_plan": _require_text(
                raw.get("evaluation_plan"), f"idea {index} evaluation_plan"
            ),
            "novelty": _rating(raw.get("novelty"), f"idea {index} novelty", low=1, high=5),
            "feasibility": _rating(
                raw.get("feasibility"), f"idea {index} feasibility", low=1, high=5
            ),
            "risks": _string_list(raw.get("risks"), f"idea {index} risks"),
            "references": _string_list(raw.get("references"), f"idea {index} references"),
            "selected": bool(raw.get("selected")),
        }
        missing = [key for key in card["references"] if allowed and key not in allowed]
        if missing:
            raise AgentPackError(
                f"idea {index} cites unknown keys: {', '.join(sorted(missing))}"
            )
        ideas.append(card)
    selected = [idea["id"] for idea in ideas if idea["selected"]]
    if len(selected) != 1:
        raise AgentPackError("exactly one idea must be selected")
    record = {
        "schema": IDEA_SCHEMA,
        "run_id": run_id,
        "topic": topic,
        "venue": str(payload.get("venue") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "selected": selected[0],
        "ideas": ideas,
        "provider_calls": 0,
        "executor": "ai-harness",
    }
    out_relative = f".paperassist/ideation/{pack_slug(run_id)}/ideas.json"
    atomic_write_text(
        root,
        out_relative,
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {"status": "ok", "path": out_relative, "selected": selected[0], "ideas": record}


# --------------------------------------------------------------------------
# Review
# --------------------------------------------------------------------------


def build_review_pack(
    workspace: str | Path,
    *,
    run_id: str,
    payload: Mapping[str, Any],
) -> AgentPack:
    root = Path(workspace).expanduser().resolve(strict=True)
    manuscript = str(payload.get("manuscript") or payload.get("main_tex") or "").strip()
    if not manuscript:
        raise AgentPackError("review requires a manuscript path")
    _, manuscript_relative = _relative(root, manuscript, what="manuscript")
    if not (root / manuscript_relative).is_file():
        raise FileNotFoundError(f"manuscript not found: {manuscript_relative}")
    venue = str(payload.get("venue") or "prestigious ML venue").strip()
    template = {
        "schema": REVIEW_SCHEMA,
        "Summary": "",
        "Strengths": [],
        "Weaknesses": [],
        "Originality": 0,
        "Quality": 0,
        "Clarity": 0,
        "Significance": 0,
        "Questions": [],
        "Limitations": [],
        "Ethical Concerns": False,
        "Soundness": 0,
        "Presentation": 0,
        "Contribution": 0,
        "Overall": 0,
        "Confidence": 0,
        "Decision": "",
    }
    tasks = [
        AgentTask(
            task_id="read-manuscript",
            phase="read",
            title="Read the manuscript and summarize it",
            skill="review-paper",
            target=f"{pack_directory(KIND_REVIEW, run_id)}/{REVIEW_FILENAME}",
            inputs={"manuscript": manuscript_relative, "venue": venue},
            instructions=(
                f"Read `{manuscript_relative}` and write the Summary exactly as the "
                "authors would accept it. Do not critique in the summary."
            ),
        ),
        AgentTask(
            task_id="evidence-audit",
            phase="audit",
            title="Audit every claim against recorded evidence",
            skill="review-paper",
            target=f"{pack_directory(KIND_REVIEW, run_id)}/{REVIEW_FILENAME}",
            instructions=(
                "For each quantitative claim, check the artifact, run log, or citation "
                "that supports it. List unsupported claims as weaknesses; never fill "
                "gaps with assumed numbers."
            ),
            depends_on=("read-manuscript",),
        ),
        AgentTask(
            task_id="score-and-decide",
            phase="score",
            title="Score the paper and decide",
            skill="review-paper",
            target=f"{pack_directory(KIND_REVIEW, run_id)}/{REVIEW_FILENAME}",
            instructions=(
                "Rate Originality, Quality, Clarity, Significance, Soundness, "
                "Presentation and Contribution from 1-4, Overall from 1-10, and "
                "Confidence from 1-5. Decision must be exactly Accept or Reject."
            ),
            depends_on=("evidence-audit",),
        ),
        AgentTask(
            task_id="revision-plan",
            phase="revise",
            title="Turn weaknesses into an ordered revision plan",
            skill="review-paper",
            target=f"{pack_directory(KIND_REVIEW, run_id)}/revision-plan.md",
            instructions=(
                "Convert every weakness and question into an actionable revision task "
                "with priority (high/medium/low) and the section it touches."
            ),
            depends_on=("score-and-decide",),
        ),
    ]
    return _write_pack(
        root,
        run_id=run_id,
        kind=KIND_REVIEW,
        payload=payload,
        tasks=tasks,
        target_name=REVIEW_FILENAME,
        target_text=json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        title=f"Review of {manuscript_relative}",
        extra={"manuscript": manuscript_relative, "venue": venue},
    )


def import_review(
    workspace: str | Path,
    *,
    run_id: str,
    result_path: str | Path,
) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve(strict=True)
    plan = load_plan(root, run_id=run_id, kind=KIND_REVIEW)
    payload = _read_result(root, result_path, what="review result")
    _reject_secrets(payload)
    review: dict[str, Any] = {
        "schema": REVIEW_SCHEMA,
        "run_id": run_id,
        "manuscript": plan.get("manuscript"),
        "Summary": _require_text(payload.get("Summary"), "Summary"),
        "Strengths": _string_list(payload.get("Strengths"), "Strengths", required=True),
        "Weaknesses": _string_list(payload.get("Weaknesses"), "Weaknesses", required=True),
        "Questions": _string_list(payload.get("Questions"), "Questions"),
        "Limitations": _string_list(payload.get("Limitations"), "Limitations"),
        "Ethical Concerns": bool(payload.get("Ethical Concerns")),
        "Overall": _rating(payload.get("Overall"), "Overall", low=1, high=10),
        "Confidence": _rating(payload.get("Confidence"), "Confidence", low=1, high=5),
    }
    for key in REVIEW_RATINGS_1_4:
        review[key] = _rating(payload.get(key), key, low=1, high=4)
    decision = str(payload.get("Decision") or "").strip()
    if decision not in REVIEW_DECISIONS:
        raise AgentPackError("Decision must be exactly Accept or Reject")
    review["Decision"] = decision
    review["provider_calls"] = 0
    review["executor"] = "ai-harness"

    out_relative = f".paperassist/review/{pack_slug(run_id)}/review.json"
    atomic_write_text(
        root,
        out_relative,
        json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    revision = _revision_tasks(review)
    atomic_write_text(
        root,
        ".paperassist/revision/review-revision.json",
        json.dumps(revision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    atomic_write_text(root, ".paperassist/revision/review-revision.md", _revision_markdown(revision))
    return {
        "status": "ok",
        "path": out_relative,
        "decision": decision,
        "revision_tasks": len(revision["tasks"]),
        "review": review,
    }


def _revision_tasks(review: Mapping[str, Any]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    items = [(item, "high") for item in review["Weaknesses"]]
    items += [(item, "medium") for item in review["Questions"]]
    for index, (instruction, priority) in enumerate(items, start=1):
        tasks.append(
            {
                "task_id": f"revision-{index:02d}",
                "priority": priority,
                "instruction": instruction,
                "status": "open",
            }
        )
    return {
        "schema": "paperassist.revision-plan/v1",
        "source": "review",
        "decision": review["Decision"],
        "tasks": tasks,
        "provider_calls": 0,
        "executor": "ai-harness",
    }


def _revision_markdown(plan: Mapping[str, Any]) -> str:
    lines = ["# Revision plan", "", f"Decision: **{plan['decision']}**", ""]
    for task in plan["tasks"]:
        lines.append(f"- [ ] `{task['task_id']}` ({task['priority']}) {task['instruction']}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Experiment
# --------------------------------------------------------------------------


def build_experiment_pack(
    workspace: str | Path,
    *,
    run_id: str,
    payload: Mapping[str, Any],
) -> AgentPack:
    root = Path(workspace).expanduser().resolve(strict=True)
    hypothesis = _require_text(payload.get("hypothesis"), "hypothesis")
    metrics = _string_list(payload.get("metrics"), "metrics", required=True)
    success = str(payload.get("success_criteria") or "").strip()
    dataset = str(payload.get("dataset") or "").strip()
    template = {
        "schema": EXPERIMENT_SCHEMA,
        "run_id": run_id,
        "status": "BLOCKED",
        "command": "",
        "code_paths": [],
        "metrics": {},
        "artifacts": [],
        "notes": "Record the command, metrics and artifact hashes after the run.",
    }
    pack_dir = pack_directory(KIND_EXPERIMENT, run_id)
    tasks = [
        AgentTask(
            task_id="implement",
            phase="code",
            title="Implement the smallest runnable experiment",
            skill="run-experiment",
            target=f"{pack_dir}/plan.md",
            inputs={"hypothesis": hypothesis, "dataset": dataset},
            instructions=(
                "Write the code inside the workspace, pinned to the stated dataset and "
                "metrics. Keep it runnable with one command and log the seed."
            ),
        ),
        AgentTask(
            task_id="static-check",
            phase="check",
            title="Static check before spending compute",
            skill="run-experiment",
            target=f"{pack_dir}/plan.md",
            instructions=(
                "Check imports, data paths, and metric definitions. Record the exact "
                "command that will run and the expected runtime."
            ),
            depends_on=("implement",),
        ),
        AgentTask(
            task_id="mini-run",
            phase="mini",
            title="Run a tiny smoke experiment",
            skill="run-experiment",
            target=f"{pack_dir}/plan.md",
            instructions=(
                "Run on a small subset with a fixed seed. Confirm the pipeline produces "
                "every declared metric before the full run."
            ),
            depends_on=("static-check",),
        ),
        AgentTask(
            task_id="full-run",
            phase="run",
            title="Run the full experiment and record artifacts",
            skill="run-experiment",
            target=f"{pack_dir}/{EXPERIMENT_FILENAME}",
            inputs={"metrics": metrics, "success_criteria": success},
            instructions=(
                "Run the full experiment. Fill `command`, `metrics`, and `artifacts` "
                f"with real values for: {', '.join(metrics)}. "
                "Each artifact needs its workspace path and sha256."
            ),
            depends_on=("mini-run",),
        ),
    ]
    return _write_pack(
        root,
        run_id=run_id,
        kind=KIND_EXPERIMENT,
        payload=payload,
        tasks=tasks,
        target_name=EXPERIMENT_FILENAME,
        target_text=json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        title=hypothesis,
        extra={"expected_metrics": list(metrics), "success_criteria": success},
    )


def import_experiment(
    workspace: str | Path,
    *,
    run_id: str,
    result_path: str | Path,
) -> dict[str, Any]:
    root = Path(workspace).expanduser().resolve(strict=True)
    plan = load_plan(root, run_id=run_id, kind=KIND_EXPERIMENT)
    payload = _read_result(root, result_path, what="experiment result")
    _reject_secrets(payload)
    status = str(payload.get("status") or "").strip().upper()
    if status not in EXPERIMENT_STATUSES:
        raise AgentPackError(
            "experiment status must be one of " + ", ".join(sorted(EXPERIMENT_STATUSES))
        )
    command = str(payload.get("command") or "").strip()
    if not command:
        raise AgentPackError("experiment result must record the command that ran")
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, Mapping) or not raw_metrics:
        raise AgentPackError("experiment result must contain a non-empty metrics object")
    metrics = {
        str(key): _metric_value(value, f"metric {key}")
        for key, value in raw_metrics.items()
    }
    expected = list(plan.get("expected_metrics") or ())
    missing = [key for key in expected if key not in metrics]
    if missing:
        raise AgentPackError("experiment result is missing metrics: " + ", ".join(missing))
    code_paths = _string_list(payload.get("code_paths"), "code_paths", required=True)
    for relative in code_paths:
        _, resolved = _relative(root, relative, what="code path")
        if not (root / resolved).exists():
            raise FileNotFoundError(f"code path not found: {resolved}")
    artifacts = _verify_artifacts(root, payload.get("artifacts"))
    if status == "COMPLETED" and not artifacts:
        raise AgentPackError("a COMPLETED experiment must record at least one artifact")
    record = {
        "schema": EXPERIMENT_SCHEMA,
        "run_id": run_id,
        "hypothesis": plan.get("title"),
        "status": status,
        "command": command,
        "code_paths": code_paths,
        "metrics": metrics,
        "artifacts": artifacts,
        "notes": str(payload.get("notes") or "").strip(),
        "provider_calls": 0,
        "executor": "ai-harness",
    }
    out_relative = f".paperassist/experiments/{pack_slug(run_id)}/result.json"
    atomic_write_text(
        root,
        out_relative,
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {"status": "ok", "path": out_relative, "result": record}


def _verify_artifacts(root: Path, raw: object) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        raise AgentPackError("artifacts must be a list")
    verified: list[dict[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise AgentPackError(f"artifact {index} is not a JSON object")
        _, relative = _relative(root, item.get("path") or "", what=f"artifact {index} path")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"artifact not found: {relative}")
        declared = str(item.get("sha256") or "").strip().lower()
        actual = sha256_file(path)
        if declared != actual:
            raise AgentPackError(f"artifact hash mismatch: {relative}")
        verified.append({"path": relative, "sha256": actual})
    return verified


# --------------------------------------------------------------------------
# Shared validation helpers
# --------------------------------------------------------------------------


def _read_result(root: Path, raw: str | Path, *, what: str) -> dict[str, Any]:
    _, relative = _relative(root, raw, what=what)
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"{what} not found: {relative}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentPackError(f"{what} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise AgentPackError(f"{what} must be a JSON object")
    return payload


def _reject_secrets(payload: Mapping[str, Any]) -> None:
    if contains_secret(dict(payload)):
        raise AgentPackError("result contains secret-like content")


def _require_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AgentPackError(f"`{field_name}` must be a non-empty string")
    return text


def _rating(value: object, field_name: str, *, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        else:
            raise AgentPackError(f"`{field_name}` must be an integer {low}-{high}")
    if not low <= int(value) <= high:
        raise AgentPackError(f"`{field_name}` must be between {low} and {high}")
    return int(value)


def _string_list(value: object, field_name: str, *, required: bool = False) -> list[str]:
    if value is None:
        value = []
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise AgentPackError(f"`{field_name}` must be a list of strings")
    items = [str(item).strip() for item in value if str(item).strip()]
    if required and not items:
        raise AgentPackError(f"`{field_name}` must not be empty")
    return items


def _metric_value(value: object, field_name: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AgentPackError(f"`{field_name}` must be a number")
    return value


def _positive_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AgentPackError("`num_ideas` must be a positive integer")
    return value


def _bibliography_keys(root: Path, payload: Mapping[str, Any]) -> tuple[str, ...]:
    from .writing_pack import parse_bib_entries

    raw = payload.get("bibliography_path") or "references.bib"
    _, relative = _relative(root, raw, what="bibliography")
    path = root / relative
    if not path.is_file():
        return ()
    entries = parse_bib_entries(path.read_text(encoding="utf-8"))
    return tuple(sorted({entry["key"] for entry in entries if entry["key"]}))


__all__ = [
    "AgentPack",
    "AgentPackError",
    "AgentTask",
    "EXPERIMENT_FILENAME",
    "IDEAS_FILENAME",
    "KIND_EXPERIMENT",
    "KIND_IDEATION",
    "KIND_REVIEW",
    "PACK_ROOT",
    "REVIEW_FILENAME",
    "build_experiment_pack",
    "build_ideation_pack",
    "build_review_pack",
    "import_experiment",
    "import_ideation",
    "import_review",
    "load_plan",
    "load_task",
    "pack_directory",
    "pack_slug",
]
