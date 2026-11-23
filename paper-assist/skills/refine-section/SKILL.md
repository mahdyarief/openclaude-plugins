---
name: refine-section
description: Section-level refinement. Tighten logic, wording and structure in a single section.
---

# Refine Section

## Purpose

Refine one section locally while the global state machine stays untouched.

## Input

- `section_name`
- `section_text`
- `tips`
- `error_list`
- `style_policy`

## Output

- refined section text
- optional summary of the changes

## Default style policy for Indonesian academic prose

When `style_policy` is empty or generic, apply these rules on top of it:

- Replace generic openers and filler with a paper-specific claim: for example,
  "dalam dunia yang semakin...", "di era digital", "tidak dapat dipungkiri",
  "perlu diingat bahwa", "memainkan peran penting",
  "secara komprehensif dapat disimpulkan".
- Vary sentence structure only where it improves clarity; never rework
  sentence lengths into a mechanical pattern.
- Keep standard academic and technical vocabulary ("signifikan", "literatur",
  "komprehensif") when it is the precise term.
- Never introduce Markdown formatting, conversational contractions, or
  blog-style asides into LaTeX prose.

These rules change wording, not claims. Citations and numbers must survive
the refinement unchanged.

## Boundaries

This skill does:
- refine a single section

This skill does not:
- decide whether another round runs
- change global writeup state
- update checkpoints
- compile the PDF

## Typical use

- refining a section right after the init draft
- section-by-section polish in the second refinement pass
