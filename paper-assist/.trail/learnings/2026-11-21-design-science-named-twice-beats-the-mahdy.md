---
title: Design science named twice beats the ML or system words of the artefact it builds
author: Mahdy
date: 2026-11-21
branch: main
cost: { minutes: 33, tokens: 206129 }
id: l-7107fbbd
scope: repo
status: active
src: agent
touches:
  - CHANGELOG.md
  - README.md
  - mcp_servers/paperassist/server.py
  - paperassist/quality/_base.py
  - paperassist/quality/compliance.py
  - paperassist/quality/method.py
  - paperassist/quality/scoring.py
  - paperassist/quality/structure.py
  - paperassist/quality/style.py
  - paperassist/research_os.py
---

## Decided
- A thesis that builds an artefact with an LLM names the LLM on every page and
  DSR only in its method; counting hits made it an ML experiment (12 vs 2 on
  the user's ICD harness draft). Design science now outranks `ml_experiment`
  and `engineering_research` once it is named twice: DSR names a methodology,
  the others name what the artefact is made of.
- In a thesis the design is stated in BAB III, past the 20,000-character
  detection window, so detection also reads the method chapter.
- RQ trace matches a section by its label (RQ1, rumusan masalah 1) or 60% of
  the question's distinctive words (those not shared by every question). A miss
  says "not traced", and the remedy is to label the section, not to reword it.

## Tried and ruled out
- Raising the detection window for all documents: article detection is
  calibrated on the opening, and the 242 calibration texts must not move.

## Watch out
- `outranks` pops designs while iterating; a popped design must not be looked
  up again (KeyError once two designs are outranked).
- Python heredocs in this shell halve backslashes: `\ref` became a carriage
  return and `\bibliographystyle` a backspace in the docs. Edit docs with the
  Edit tool and scan for control characters before committing.

In the code: `paperassist/research_designs.py` (design_science.outranks,
detection_text, detect_research_design), `paperassist/thesis_extras.py`.
