---
title: "Detection reads the paper's own claims, not what it cites or denies"
author: Mahdy
date: 2026-11-21
branch: main
cost: { minutes: 13, tokens: 85193 }
id: l-972e1f87
scope: repo
status: active
src: agent
touches:
  - CHANGELOG.md
  - README.md
  - mcp_servers/paperassist/server.py
  - paperassist/analysis_checks.py
  - paperassist/participant_flow.py
  - paperassist/quality/method.py
  - paperassist/quality/scoring.py
  - paperassist/reporting_checks.py
  - paperassist/research_designs.py
  - paperassist/research_os.py
---

## Decided
- Design and family detection read `detection_text`: body before the last references heading, PRISMA's spelled-out name removed, and denied designs removed ("a meta-analysis was not conducted", "rather than an exhaustive systematic review"). On 86 thesis reference papers an editorial became a systematic review from its reference list, and a review that refused meta-analysis became one.
- CS literature surveys ("...: A Survey", "In this survey, we review") are reviews unless the paper has 2+ questionnaire/respondent words; four RAG/agent surveys had been read as ML experiments.
- Scoping and bibliometric reviews named twice outrank systematic_review (`outranks`), because they select records with PRISMA.

## Tried and ruled out
- "brief survey" and "critical review" as review markers: empirical papers use both in background prose ("a critical review of existing literature reveals"), which turned an observational BPJS study into a review.

## Watch out
- Methodology essays (Hevner, Peffers, Okoli) detect as the design they discuss; that is expected, not a bug.

In the code: paperassist/research_designs.py (detection_text, _NEGATED_MENTIONS, _REFERENCES_HEADING, LITERATURE_SURVEY_RE, outranks), paperassist/reporting_checks.py (detect_paper_type, _QUESTIONNAIRE_RE), tests/test_detection_calibration.py.
