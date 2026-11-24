---
name: slr
description: SLR assistant (Kitchenham + PRISMA 2020) — status, start a project, or run a stage
argument-hint: "[status|mulai|cari|saring|fulltext|kualitas|ekstrak|sintesis|lapor|prisma] <folder>"
---

Load the `slr-assist` skill (`${CLAUDE_PLUGIN_ROOT}/skills/slr-assist/SKILL.md`) and follow it.
The tool is `python "${CLAUDE_PLUGIN_ROOT}/skills/slr-assist/scripts/slr.py"`.

Arguments: `$ARGUMENTS`

- No argument or `status <folder>`: run `slr.py status <folder>` and report the stage, queues,
  warnings and the single next step in plain words. If no folder is given and none is obvious
  from the working directory, ask for it.
- `mulai <folder>`: run `slr.py init <folder>`, then start stage 1 (planning) with the
  first protocol section only (need for the review).
- `prisma <folder>`: run `slr.py rekap <folder> --simpan` and show the diagram and warnings.
- Any other stage word: run `status` first, then work on that stage following
  `references/alur-kerja.md`. Never run `sahkan` unless the researcher approved in this conversation.

Reply in the researcher's language. One proposal and at most one question per turn.
