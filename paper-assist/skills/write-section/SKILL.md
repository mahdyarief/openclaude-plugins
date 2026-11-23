---
name: write-section
description: Section-level paper writing. Draft a single section without taking over the writing pack workflow.
---

# Write Section

## Purpose

Write one section at a time. This skill does not own the pipeline, the stage
order or the round budget.

## Input

- `section_name`
- `notes`
- `idea_metadata`
- `style_policy`
- `existing_tex_context`

## Output

- draft text for a single section
- optional in-section structural suggestions

## Default style policy for Indonesian academic prose

When `style_policy` is empty or generic, apply these rules on top of it:

- Avoid generic openers and filler such as "dalam dunia yang semakin...",
  "di era digital", "tidak dapat dipungkiri", "perlu diingat bahwa",
  "memainkan peran penting", "secara komprehensif dapat disimpulkan".
  Open with a paper-specific claim instead.
- Vary sentence structure only where it improves clarity.
- Keep standard academic and technical vocabulary ("signifikan", "literatur",
  "komprehensif") when it is the precise term.
- No Markdown formatting, conversational contractions, or blog-style asides
  in the LaTeX draft.

## Boundaries

This skill does:
- write one section

This skill does not:
- decide whether cite / refine / latex_fix runs next
- decide the next phase
- modify global checkpoints
- write the final PDF

## Typical sections

- Introduction
- Background
- Method
- Experimental Setup
- Results
- Conclusion
