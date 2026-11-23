---
name: research-workflow
description: Drive the PaperAssist MCP tools end to end. Use when the user wants to plan ideas, review a manuscript, define an experiment, draft a paper or thesis in LaTeX, audit claims against a study corpus, or verify that a revision did not lose evidence.
---

# Research Workflow

## Purpose

PaperAssist ships no language model. You (the harness) do the thinking and
writing; PaperAssist plans the work, binds evidence and refuses results that
fail its deterministic gates. This skill is the order in which to call the
tools. The section skills (`write-section`, `refine-section`,
`citation-gap`, `citation-select`, `de-aigc-rewrite`, `latex-fix`) are used
inside these loops for one unit of work at a time.

Call `harness_status` once per workspace first. Every tool returns a
`status`; a failed call comes back with `isError: true` and a message naming
the accepted arguments. Read it and fix the call rather than guessing again.

## Loop A: ideation, review or experiment pack

1. `pack_scaffold` with `workspace`, `kind` (`ideation`, `review` or
   `experiment`) and the inputs for that kind (`topic`, `venue`,
   `manuscript`, `hypothesis`, `dataset`, `metrics`, ...). Keep the returned
   `run_id`.
2. Read `plan.json` and `agent-brief.md` (`pack_plan`), then each task
   (`pack_task`) in order.
3. Do the tasks. Write the result into the pack's target file
   (`ideas.json`, `review.json` or `experiment.json`).
4. `pack_import` with `kind`, `run_id` and `result_path`. If a gate rejects
   it, fix the reported fields and import again. Never edit the gate.

## Loop B: LaTeX paper or thesis draft

1. Optionally `journal_lookup` or `thesis_lookup` for format rules; a thesis
   profile goes in as `thesis_profile: {"profile_id": "..."}`, and its
   preamble (margins, spacing, font) then heads the skeleton.
2. `writing_pack` with `topic`, `title`, and for a thesis
   `document_kind: "thesis"` plus `thesis_type`; add `thesis_stage:
   "proposal"` for a seminar proposal (Chapters 1-3 only). The approval page,
   originality statement, preface and English abstract are the author's:
   leave them for the student to fill, as with the Declarations block.
3. Work through `writing_task` items in order: sections, citation rounds,
   refinement, evidence reconciliation. Cite only keys the plan allows.
   Experimental Setup and Results are the authors' and live inside the
   protected experiment block; in the Discussion restate only numbers that
   appear there, or point at its tables with `\ref`. Never write the
   Declarations block (funding, interests, data, CRediT, AI use): ask the
   authors to fill it.
4. `writing_import` with `run_id` and `draft_path` (or `draft_text`).
5. For a local fix afterwards use `writing_patch` on one unique `anchor`,
   passing the SHA-256 of the file as you read it (`source_sha256`), instead
   of rewriting the file. It only patches a `.tex` file that holds a
   protected experiment block, and refuses `\input`, `\write18`, macro
   definitions and other unsafe LaTeX in the replacement.

## Loop C: Research OS audit and revision

1. `research_os` with `target_path` and, when available, `records_path`,
   `fulltext_root`, `bibliography_path` and `source_path`. For a review add
   the PRISMA flow document to `records_paths` (or, for a trial or
   observational study, the CONSORT/STROBE counts to `participant_flow`);
   check `design_detection` in `reporting-checks.json`, and set `research_design`
   (`design_lookup` lists them: rct, survey, qualitative, design_science,
   research_development, classroom_action_research, ...) when `auto` guesses
   wrong, and `journal_profile` or `required_declarations` for the
   target venue. For a thesis, `document_kind` and `thesis_stage` default to
   `auto`; pass `thesis_profile` (the campus profile id) and, when the guide
   differs, `required_front_matter`. Check the `thesis` block in
   `reporting-checks.json`: missing front matter, Chapter 1 elements, whether
   research questions, objectives and conclusions line up, the `trace` of
   each research question through the method, results and conclusion
   chapters, the two abstracts, captions and citation style, and layout. When
   a question is not traced, label the section that answers it (RQ1) rather
   than restating the question.
   Artifacts land in `.paperassist/research-os/<run_id>/`;
   start from `index.md` and `reporting-checks.json`.
2. Work the `revision-plan.json` findings from the top.
3. Rewrite only sentences in `narrative.jsonl`. Sentences in
   `evidence.jsonl` keep their claim, citation, locator and numbers; add a
   `% @locator{key: page=..., quote="..."}` when you strengthen grounding.
4. Save the revision to a new file and run `improvement_verify` with
   `before_path` and `after_path`. If it is not `accepted`, revert the
   regressing change instead of arguing with the verdict.

Use `corpus_bind`, `claim_audit` or `quality_score` alone when the user
asks for only that stage.

## Boundaries

This skill does not:
- invent data, metrics, baselines, hardware or citations
- edit protected experiment blocks or `evidence.jsonl` content
- bypass, weaken or re-implement an import gate
- decide scientific conclusions for the researcher
