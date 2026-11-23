---
name: de-aigc-rewrite
description: De-mechanicalise prose. Compress templated phrasing and obvious AI tone without changing the argument.
---

# De-AIGC Rewrite

## Purpose

Rewrite a paragraph or section once to remove mechanical style, keeping facts
and structure intact.

## Input

- `text`
- `style_goal`

## Output

- `rewritten_text`
- `style_notes`

## Editorial policy for Indonesian academic prose

- Replace generic openers and filler with a paper-specific claim: for example,
  "dalam dunia yang semakin...", "di era digital", "tidak dapat dipungkiri",
  "perlu diingat bahwa", "memainkan peran penting",
  "secara komprehensif dapat disimpulkan". Keep one only when the surrounding
  evidence makes the wording genuinely precise.
- Vary sentence structure where it improves clarity; do not force an
  artificial short/long pattern.
- Keep standard academic and technical vocabulary (including "signifikan",
  "literatur", "komprehensif") when it is the precise term.
- No conversational contractions, blog-style asides, or Markdown formatting
  inside LaTeX prose.

## Boundaries

This skill does:
- compress expression
- cut templated openings and filler

This skill does not:
- change experimental conclusions
- invent citations
- take over the writeup pipeline
