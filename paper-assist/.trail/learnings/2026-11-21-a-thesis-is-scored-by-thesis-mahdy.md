---
title: "A thesis is scored by thesis rules, and a proposal is not penalised for results it cannot have"
author: Mahdy
date: 2026-11-21
branch: main
cost: { minutes: 87, tokens: 440080 }
id: l-847c20d5
scope: repo
status: active
src: agent
touches:
  - ".claude-plugin/marketplace.json"
  - ".claude-plugin/plugin.json"
  - CHANGELOG.md
  - README.md
  - mcp_servers/stdio.py
  - paperassist/__init__.py
  - pyproject.toml
  - tests/test_mcp_server.py
  - tests/test_version.py
  - mcp_servers/paperassist/server.py
---

## Decided
- Thesis mode swaps rules inside the existing fourteen dimensions instead of adding a fifteenth: front matter (approval page, originality statement, abstracts) is scored in `declarations` in place of journal declarations; Chapter 1 elements and question/objective/conclusion counts go in `structure`; layout against the thesis profile is info only. Keeping the dimension set fixed keeps weights, grades and every article score unchanged.
- In a document that uses chapter headings, a section heading is a subsection of its chapter. Without this, the body of "BAB III Metodologi" ended at its first section ("3.1 Data") and the method was judged on one paragraph.
- Two thesis stages. A proposal (Chapters 1-3) requires only title page, approval page and table of contents, has no abstract or limitations scored, and its method is judged as a plan (no results component). Auto picks proposal when the title says so or no results/conclusion chapter exists.
- Calibrated on the user's real Bab 1-2 draft: before the stage, it scored D on missing results and conclusion it could not yet have; after, only Bab III, the approval page and ethics remained.

## Tried and ruled out
- Treating "Batasan Masalah" as the limitations statement: it is the scope (delimitation), not the limitations of a finished study; limitations come from a Keterbatasan subsection or sentences in the closing chapter.
- Enforcing the Telkom 40,000-100,000 word rule: the guide states it for Magister Manajemen only, so `word_range` stays unset on that profile.

## Watch out
- Profile front matter is prose ("abstrak (Indonesia dan Inggris)"); new profiles must use words the mapping in thesis_checks recognises, or the item is not required.

In the code: paperassist/thesis_checks.py (resolve_document_kind, resolve_thesis_stage, check_thesis, PROPOSAL_FRONT_MATTER), paperassist/quality/_base.py (_section_bodies nested_levels), paperassist/quality/compliance.py (_dimension_thesis_statements), paperassist/quality/scoring.py (THESIS_DEPTH_TARGET), paperassist/writing_skeletons.py (_thesis_skeleton thesis_stage).
