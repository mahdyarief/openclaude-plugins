---
title: "Workspace containment must reject '..' segments, not just compare paths lexically"
author: Mahdy
date: 2026-11-20
branch: main
cost: { minutes: 18, tokens: 166495 }
id: l-8c7c2be9
scope: repo
status: active
src: agent
touches:
  - mcp_servers/base.py
  - skills/research-workflow/SKILL.md
  - tests/test_mcp_server.py
  - tests/test_harness_and_lock.py
  - tests/test_agent_packs.py
  - tests/test_safety_guards.py
  - tests/test_writing_patch.py
  - tests/test_path_safety_and_memory.py
  - ".claude-plugin/marketplace.json"
  - tests/test_release_consistency.py
---

## Decided
- `reject_symlink_components` rejects any `..` in the path when an anchor is given.
  `Path.absolute()` keeps `..`, so `ws/../other.tex` passed `relative_to(ws)` and
  `writing_patch` could overwrite a `.tex` outside the workspace.
- Callers that read files should use `research_os._resolve_source` /
  `read_workspace_text`, which also `resolve()` and re-check containment.

## Tried and ruled out
- Relying on `lexical.relative_to(anchor)` alone: it is purely lexical and never
  collapses `..`.

## Watch out
- `task_id` is a file stem in `load_task` / `load_writing_task`; it is validated
  against `[A-Za-z0-9][A-Za-z0-9._-]*` because `run_id` is slugged but task ids were not.

In the code: paperassist/path_safety.py (reject_symlink_components),
paperassist/writing_patch.py (_resolve_target), paperassist/agent_packs.py (_check_task_id),
tests/test_path_safety_and_memory.py, tests/test_writing_patch.py
