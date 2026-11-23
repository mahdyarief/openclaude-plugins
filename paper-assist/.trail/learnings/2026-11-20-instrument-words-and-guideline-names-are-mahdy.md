---
title: Instrument words and guideline names are not evidence of a research design
author: Mahdy
date: 2026-11-20
branch: main
cost: { minutes: 20, tokens: 274235 }
id: l-b31bc007
scope: repo
status: active
src: agent
touches:
  - CHANGELOG.md
  - README.md
  - mcp_servers/README.md
  - mcp_servers/paperassist/server.py
  - mcp_servers/writing/server.py
  - paperassist/quality/_base.py
  - paperassist/quality/method.py
  - paperassist/quality/scoring.py
  - paperassist/reporting_checks.py
  - paperassist/research_designs.py
---

## Decided
- Design detection ignores the spelled-out PRISMA name ("Preferred Reporting Items for Systematic Reviews and Meta-Analyses") and a meta-analysis needs two mentions. Calibrating on real Indonesian SLRs showed every one of them cites PRISMA in full, so the child-beats-parent rule turned each SLR into a meta-analysis.
- Questionnaire words (kuesioner, angket, questionnaire) are weak evidence: they count towards a survey only when no other empirical design of the family names itself. A real ADDIE R&D article had 14 angket/kuesioner mentions against 11 R&D mentions and was scored as a survey.
- Aiken's V values are matched with straight and curly apostrophes and as ranges ("berkisar antara 0,64 hingga 0,73"); published articles use both.
- Analysis checks (N-gain, Aiken's V, prerequisite tests) are advisory findings and do not move the method score until they have been calibrated on more papers.

## Tried and ruled out
- Raising the survey min_hits further: an R&D paper can mention angket more often than its own design, so no count threshold separates them; the rival-design rule does.
- Reading survey weak hits as strong when the paper also says "metode survei": kept simple, only the strong phrase list counts then.

## Watch out
- Calibration ran on pdftotext output converted to LaTeX by a heading heuristic; inline headings ("METODE PENELITIAN Penelitian ini...") are missed, so a method score of 0 on PDF-derived text is a conversion artefact, not a finding.
- Do not commit the downloaded article texts; regression tests use short paraphrased sentences.

In the code: paperassist/research_designs.py (_GUIDELINE_EXPANSIONS, weak_detect, _counted_hits, explain_detection), paperassist/analysis_checks.py (_AIKEN_VALUE_RE, _AIKEN_RANGE_RE), tests/test_research_designs.py and tests/test_design_followups.py.
