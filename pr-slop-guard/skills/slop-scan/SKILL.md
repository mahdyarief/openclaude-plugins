---
name: slop-scan
description: This skill should be used when the user asks to "check this PR for slop", "is this diff AI slop", "review this diff for low-quality AI code", "scan staged changes for slop", or "triage this pull request". Detects AI-generated low-quality code before a PR is opened.
version: 0.1.0
---

# Slop Scan — PR Slop Detection

Detect AI-generated low-quality code ("slop") in a git diff in two layers:
static scan first (deterministic, seconds), LLM judgment second (semantic only).

## Procedure

To scan a diff for slop, do the following:

1. **Obtain the diff.** Prefer `git diff <base>...HEAD` for a branch, or
   `git diff --staged` for pre-PR local check. Save to a temp file.
2. **Run the static scanner** (no LLM cost, always first):
   `python "${CLAUDE_PLUGIN_ROOT}/skills/slop-scan/scripts/slop_scan.py" --diff-file <diff>`.
   Record the JSON `verdict` (SLOP / SUSPECT / CLEAN) and findings list.
3. **Judge semantically** only the findings that need context — never re-scan
   what the static layer already decided:
   - SLP-04 (auth-or): read the surrounding function; confirm whether `or`
     matches the intended authorization rule and whether any operand trusts
     client-controlled input.
   - Confident hallucination: for any unfamiliar method/config key in the diff,
     verify it exists in the real library (read installed source or docs, do not
     trust the diff's tone). See `references/patterns.md` P1-3.
   - SLP-07 candidates / Fake Test: for each test in the diff, state what would
     have to break in real code for it to fail. If nothing, mark fake.
   - Over-abstraction: flag any new interface/ABC with exactly one implementation.
4. **Emit the verdict table** in this exact shape:

   Verdict: SLOP | SUSPECT | CLEAN
   | Severity | Rule | File:Line | Note |
   |---|---|---|---|
   | P1 | ... | ... | ... |

   Then one recommended action: `request-revision` (any P1), `comment-label`
   (`slop` label when 2+ P1 or author is external first-time contributor),
   `close-PR` (only when P1 >= 3 and no test coverage at all), or `approve`
   (CLEAN).

## Rules

- Run the static script before any LLM judgment; do not skip it.
- Mirror CodeRabbit semantics: slop detection is advisory, never a merge block
   on its own. Exempt repo collaborators/owners/bots from the `slop` label;
   target external low-quality contributions.
- Keep output tight: table plus one action line. Move pattern details to
   `references/patterns.md`; do not paste them into the verdict.

## Additional Resources

- **`references/patterns.md`** — the 12 Potapov slop patterns (P1/P2/P3) with
  examples; consult when judging SLP-04, hallucination, fake tests.
