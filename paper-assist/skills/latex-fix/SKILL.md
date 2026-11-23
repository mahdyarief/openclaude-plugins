---
name: latex-fix
description: LaTeX repair. Fix one round of compile errors or chktex diagnostics without owning the writeup state machine.
---

# LaTeX Fix

## Purpose

Apply one local repair to the current LaTeX text without changing the writeup
stage order.

## Input

- `latex_text`
- `diagnostics`
- `current_round`

## Output

- repaired `latex_text`
- `fixes_applied`

## Boundaries

This skill does:
- one round of LaTeX text repair
- consolidating diagnostics

This skill does not:
- control the total latex_fix round budget
- update checkpoints
- decide when writeup ends
