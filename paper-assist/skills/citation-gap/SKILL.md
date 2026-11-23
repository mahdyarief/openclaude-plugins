---
name: citation-gap
description: Citation gap detection. Identify the single most important missing citation in the draft and produce a query.
---

# Citation Gap

## Purpose

During citation rounds, find the most important citation gap in the current
draft.

## Input

- `draft`
- `current_round`
- `total_rounds`

## Output

- `Description`
- `Query`

## Boundaries

This skill does:
- find the gap
- produce the query

This skill does not:
- search external literature itself
- pick the final reference
- write the citation back into the draft
