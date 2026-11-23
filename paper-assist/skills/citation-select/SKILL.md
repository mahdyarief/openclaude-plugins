---
name: citation-select
description: Candidate selection. Pick the references from a search result that best fit the current manuscript.
---

# Citation Select

## Purpose

During citation rounds, choose the most relevant references from a candidate
search result.

## Input

- `papers`
- `draft_context`
- `current_description`

## Output

- `Selected`
- `Description`

## Boundaries

This skill does:
- select from candidate literature
- update the description

This skill does not:
- run the external search
- write bibtex into references
- edit the tex file
