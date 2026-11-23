# Changelog

## 4.2.0 — 2026-11-21

### Thesis checks across chapters

- `paperassist.thesis_extras`: each Chapter 1 research question is traced to
  the method, results and conclusion chapters by its label (RQ1, "rumusan
  masalah 1", "tujuan pertama") or most of its distinctive words
  (`ThesisCheck.trace`); a proposal is traced to its method chapter only.
- Abstrak and English abstract: word and paragraph limits read from the
  profile's `abstract_layout`, the same keyword count, the same numbers.
- Tables and figures: table captions above, figure captions below, numbering
  per chapter, a text reference before the float (`tables_figures`).
- Citation style: the declared bibliography style against the profile's
  `citation_style`, and typed numeric and author-year citations never mixed
  (`references`). `ReferencePolicy.min_entries` and
  `ThesisProfile.reference_policy` set a minimum reference count.
- Design detection: design science named twice outranks `ml_experiment` and
  `engineering_research`, and in a thesis the method chapter is read even when
  it lies past the first 20,000 characters. Unchanged on the 242 calibration
  texts.
- Fixed a broken `\ref` in the README ownership table.

### Thesis mode across Research OS

- `paperassist.thesis_checks`: `resolve_document_kind` (article/thesis/auto),
  `resolve_thesis_stage` (proposal/final/auto) and `check_thesis`, covering
  front matter against the thesis profile, the Chapter 1 elements, research
  question/objective/conclusion counts, preamble layout (font size, paper,
  line spacing, geometry margins) and an optional word range.
- `score_manuscript`, `quality_score` and `research_os` take `document_kind`,
  `thesis_profile`, `thesis_stage` (and `required_front_matter` in
  `research_os`). For a thesis, `declarations` scores the thesis statements
  instead of journal declarations. `structure` carries the Chapter 1 and
  alignment findings. `depth` targets 1,500 words per chapter, and the
  abstract may be a `\chapter*{Abstrak}`. `limitations` accepts statements in
  the closing chapter. `QualityReport.document_kind` and
  `reporting-checks.json` report all of it.
- Proposal stage: Chapters 1–3 are required. Abstract and limitations are not
  scored, and the method is judged as a plan.
- Section parsing: in a document with `\chapter`, a `\section` is a
  subsection and no longer cuts the chapter body short. New aliases:
  Metodologi, Landasan Teori, Kajian Pustaka, Simpulan, Penutup, Pengujian.
  Labels placed right after headings are no longer reported as unreferenced.
  The abstract check now recognises empirical method words.
- Writing pack: the thesis skeleton adds author-owned front-matter pages,
  Chapter 1 and closing-chapter outlines, and the profile preamble when
  `thesis_profile.profile_id` is set. `thesis_stage: "proposal"` builds a
  Chapter 1–3 proposal with tasks for those chapters only.
- `ThesisProfile.word_range` (optional).

## 4.1.0 — 2026-11-21

### Non-empirical papers, benchmarks and systems

- Third design family, `conceptual`: `methodological_paper` (essays, guides,
  research methodologies) and `position_paper` (editorials, commentaries,
  perspectives), after Wieringa et al.'s philosophical and opinion papers.
  Detected from the article-type label in the opening (`article_type_label`),
  judged on the whole text, and not asked for ethics or code availability.
- `dataset_benchmark` (Datasheets for Datasets; NeurIPS D&B) outranks
  `ml_experiment` when a paper releases a resource; a benchmark title adds
  weight (`ResearchDesign.title_boost`). `engineering_research` (ACM SIGSOFT
  Engineering Research) for system and architecture papers.
- Others' reviews ("a 2025 systematic review by du Preez", "recent
  systematic review evidence") and "qualitatively" no longer count; "A survey
  of ..." titles and "this survey aims to provide" mark literature surveys.

### Detection calibrated on 86 thesis reference papers

- Reviews: computer-science literature surveys ("...: A Survey", "In this
  survey, we review") count as reviews unless the paper has respondents, and
  are classed as narrative reviews; "curated review" too.
- Detection reads the body before the reference list and drops denied designs
  ("a meta-analysis was not conducted", "Synthesis Without Meta-analysis",
  "rather than an exhaustive systematic review").
- Scoping reviews and bibliometric analyses named twice outrank the systematic
  review their PRISMA wording suggests (`ResearchDesign.outranks`).
- "PTK" in student numbers and Sugiyono's "Kuantitatif, Kualitatif, dan R&D"
  title are ignored.
- Analysis checks: word-bounded N-gain, Aiken's V only for the coefficient (not
  an author named Aiken), homoscedasticity counts as a homogeneity statement.

### Participant flow, analysis checks and design follow-ups

- CONSORT 2025 and STROBE participant-flow arithmetic
  (`paperassist.participant_flow`): enrolment, allocation across arms,
  intervention received, analysis per arm, and STROBE stages that may not grow.
  RCTs and quasi-experiments (TREND) use the CONSORT flow, observational
  studies the STROBE flow. `research_os` takes `participant_flow` (object or
  path) or a count document; `quality_score` takes `flow_path` (PRISMA,
  CONSORT or STROBE, whichever the design uses). `FlowIdentity` gains a
  `relation` (`=` or `<=`) and `FlowCheck` a `kind`.
- Advisory analysis checks (`paperassist.analysis_checks`) for quantitative,
  mixed, R&D and action-research designs: N-gain categories against Hake's
  bounds, Aiken's V range plus stated raters and rating categories, and
  normality and homogeneity tests before t-tests, ANOVA and ANCOVA.
- Design detection explains itself (`explain_detection`): candidates, matched
  phrases and a confidence rating, in `design_lookup` and in
  `reporting-checks.json` (`design_detection`).
- Calibrated on open-access Indonesian articles: the spelled-out PRISMA name no
  longer counts as a meta-analysis (which now needs two mentions), and
  questionnaire words count towards a survey only when no other empirical
  design is named (R&D and PTK use angket too).
- Every design has a suggested Method outline, added to the writing brief and,
  as comments, to the paper and thesis skeletons (`research_design`).
- Verified item counts: STARD 2015 (30 items), TRIPOD+AI (27), TREND (22).

### Research designs beyond systematic reviews

- New `paperassist.research_designs` registry: 20 designs in a small tree,
  each mapped to its reporting guideline and turned into Method,
  reproducibility and Results items. Evidence synthesis: systematic review
  (PRISMA 2020/PRISMA-S) with meta-analysis as a child, scoping review
  (PRISMA-ScR), bibliometric (BIBLIO), narrative review (SANRA). Quantitative:
  RCT (CONSORT 2025), quasi-experiment (TREND), observational (STROBE), survey
  (CROSS/CHERRIES), diagnostic accuracy (STARD 2015), prediction model
  (TRIPOD+AI), ML experiment (REFORMS), general empirical. Qualitative and
  mixed: qualitative (SRQR/COREQ), case study, mixed methods (GRAMMS). Design
  and development: design science (DSRM), R&D (Borg & Gall, ADDIE, 4D). Action
  research, with classroom action research (PTK, Kemmis & McTaggart) as a child.
- `research_design` for `quality_score`, `research_os` and `writing_pack`;
  `paper_type` also accepts a design key. `auto` picks the most specific design
  the manuscript names within its family, so a review about machine learning
  stays a review. Qualitative studies are no longer asked for statistics; the
  PRISMA flow applies to systematic, scoping and meta-analytic reviews.
- New MCP tool `design_lookup` (18 tools): list designs, look one up by key or
  alias, or detect it from a manuscript. Quality and reporting-check artifacts
  record the design and its guideline.

### Modularisation (no behaviour change)

- `manuscript_quality.py` (1593 lines) split into the `paperassist.quality`
  package: `_base` (types, section parsing), `structure`, `grounding`,
  `method`, `compliance`, `style` and `scoring`. `manuscript_quality` stays as
  the public import path.
- `writing_pack.py` (1500 lines) split into `writing_content` (sections,
  briefs, rules), `writing_skeletons` (LaTeX skeletons, protected blocks) and
  `writing_tasks` (task assembly); `writing_pack` keeps pack building and
  loading and re-exports the public names.

### Paper mode and Research OS reporting standards

- `paper_type` (`auto` / `review` / `empirical`) for `research_os` and
  `quality_score`. Reviews are judged on PRISMA 2020 / PRISMA-S signals (search
  dates, full search strings, independent reviewers, risk-of-bias tool,
  certainty of evidence) plus flow-diagram arithmetic; empirical papers on
  design, data, procedure, metrics, analysis, baselines, validation and
  statistical reporting (variability, effect or test, sample size).
- Two new quality dimensions (14 in total): `declarations` (competing
  interests, funding, data availability, AI-use disclosure per ICMJE/COPE,
  CRediT, ethics when human participants are involved; required set per
  `journal_profile` or `required_declarations`) and `references` (recency,
  primary-literature share via `reference_policy`, retractions from a local
  Retraction Watch CSV via `retraction_db_path`).
- Research OS verifies `@locator` quotes against the bound full text; a quote
  that is not in the source no longer counts as anchored. One grounding floor
  (0.6) for the rubric and the writing gate.
- Combined headings count for every kind they name ("Hasil dan Pembahasan",
  "Results and Discussion"); "Experimental Setup" counts as method; a
  Limitations subsection counts as a dedicated statement; figure paths resolve
  against the manuscript folder.
- Writing pack (paper): adds Discussion and Limitations, skips the
  author-owned Experimental Setup / Results by default (they live in the
  protected block and the gate refused them), and adds a protected,
  author-owned Declarations block. The import gate now accepts numbers copied
  from the protected block, rejects chat-assistant residue, and its rules say
  which checks are mechanical.
- Fixed: the "persen" unit pattern in the claim ledger held literal backspace
  characters, so "45 persen" was treated as a count; the source-coverage gap
  message stated the comparison backwards; the citations measurement used a
  different denominator from the score. `reporting-checks.json` is a new
  artifact.

### Hardening

- Security: workspace containment now rejects `..` segments. Previously
  `ws/../other.tex` passed the lexical check, so `writing_patch` could write a
  `.tex` file outside the workspace. `pack_task`/`writing_task` validate
  `task_id`, `writing_patch` `replacement_path` and Research OS `ris_paths`
  use the same containment as every other workspace read.
- MCP: every tool publishes a real `inputSchema` (names, types, defaults,
  required); unknown arguments are rejected instead of silently dropped;
  execution failures return `isError: true`; `resources/read` works with
  per-run parameters in the URI query string; only declared tools are callable.
- The run-lock wait message goes to stderr so it cannot corrupt the JSON-RPC
  stream.
- `harness_status` reads MCP servers from `plugin.json` (`.mcp.json` is
  optional and merged when present).
- Fixed the ACM profile's `template_formats` (a string, listed as `t`,`e`,`x`).
- Added the `research-workflow` skill that drives the MCP tools end to end, a
  Claude Code marketplace manifest, and tests for the MCP layer, packs,
  patching, protected blocks, LaTeX/style guards, path safety and memory.
- ruff and mypy are clean; a duplicated test that shadowed another was removed.
- Added an advisory `formulaic_prose` quality dimension that flags generic
  Indonesian phrasing and unusually uniform sentence rhythm. It is a review
  signal, not an authorship detector, and does not penalise standard academic
  vocabulary.
- Added default Indonesian anti-slop guidance to the `write-section`,
  `refine-section`, and `de-aigc-rewrite` skills and to generated section
  instructions, without changing any claims, citations, or numbers.

## 4.0.1

- Added `journal_lookup` MCP tool and `paperassist://journal-profiles` resource:
  curated, citable format references for Indonesian (SINTA/JTIM) and
  international (Elsevier/IEEE/Springer Nature/ACM) journals, plus heuristic
  `\documentclass` detection. Includes explicit note that stock `article`
  abstracts use `\small` + `quotation` (inset), not full `\textwidth`.
- Added `paperassist/journal_profiles.py` and focused tests.

## 3.0.0

- Added the unified Research OS runtime, typed agents, profiles, approvals,
  recovery, and idempotent workflow events.
- Added SQLite Scientific Memory and sentence-level Claim/Evidence publication
  gates.
- Added verified experiment provenance and six compute backend contracts.
- Added generic, CVPR, IEEE, and Elsevier publication profiles with bounded
  layout repair and deterministic source bundles.
- Added a single provider configuration/request path and fail-closed Bailu
  authentication handling.
- Added authoritative release verification, secret scanning, safe artifact
  preview, third-party source locks, and MambaIR-GPPNN writing-only delivery.
- Removed legacy Alpha documentation, generated demo results, cached
  environments, and obsolete shell-key setup.
