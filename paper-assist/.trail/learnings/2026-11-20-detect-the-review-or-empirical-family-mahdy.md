---
title: "Detect the review-or-empirical family first, then the specific research design"
author: Mahdy
date: 2026-11-20
branch: main
cost: { minutes: 21, tokens: 256437 }
id: l-0f667cb5
scope: repo
status: active
src: agent
touches:
  - CHANGELOG.md
  - paperassist/manuscript_quality.py
  - paperassist/quality/__init__.py
  - paperassist/quality/_base.py
  - paperassist/quality/compliance.py
  - paperassist/quality/grounding.py
  - paperassist/quality/method.py
  - paperassist/quality/scoring.py
  - paperassist/quality/structure.py
  - paperassist/quality/style.py
---

## Decided
- Research design detection runs in two steps: first the family (review vs empirical, from review markers and the bound corpus), then the most specific design of that family the manuscript names. A child design (meta-analysis, PTK) wins over its parent whenever it is named.
- Each design's checks come from its published reporting guideline (CONSORT 2025, STROBE, CROSS, SRQR/COREQ, PRISMA-ScR, BIBLIO, TRIPOD+AI, REFORMS, DSRM, Borg & Gall/ADDIE, Kemmis & McTaggart). Signals only show that an item is mentioned; they are not a checklist assessment.

## Tried and ruled out
- Picking the design with the most keyword hits across all designs: a systematic review about deep learning mentions ML words far more often than "systematic review", so it was scored as an ML experiment.
- A single survey keyword as evidence of a survey design: many empirical papers mention a questionnaire in passing; survey and ML designs need two hits.

## Watch out
- Guideline item counts in the registry are only stated where a source confirmed them (STARD and TRIPOD+AI counts were left out).
- Inline Python heredocs keep turning "\n" and "\b" inside string literals into real newlines/backspaces; write code with backslashes through the editor.

In the code: paperassist/research_designs.py (detect_research_design, min_hits), paperassist/reporting_checks.py (resolve_research_design), paperassist/quality/method.py (_dimension_method), tests/test_research_designs.py
