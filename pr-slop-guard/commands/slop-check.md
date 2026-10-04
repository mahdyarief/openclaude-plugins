---
description: Detect AI-generated low-quality code ("slop") in a diff before the PR is opened — static scan first, then semantic judgment; outputs SLOP / SUSPECT / CLEAN verdict table plus one recommended action.
---

# /slop-check — AI Slop Detection

Detect AI-generated low-quality code ("slop") in a diff before the PR is opened.

## Arguments
- `$ARGUMENTS` (optional): base ref to diff against (default `main`), or `--staged` for staged changes.

## Steps
1. Resolve the diff source from the argument:
   - `--staged` → `git diff --staged`
   - a ref (e.g. `main`, `develop`) → `git diff <ref>...HEAD`
   - no argument → try `git diff main...HEAD`, fall back to `git diff master...HEAD`
2. Save the diff to a temp file and run the static scanner:
   `python "${CLAUDE_PLUGIN_ROOT}/skills/slop-scan/scripts/slop_scan.py" --diff-file <tmp>`
3. For each finding that needs context (SLP-04 auth-or, hallucinated APIs, SLP-07 fake tests, single-impl abstractions), read the surrounding code and confirm or dismiss it. Do not re-flag what the scanner already cleared.
4. Follow the `slop-scan` skill procedure for the final output:
   verdict table (SLOP / SUSPECT / CLEAN) plus one recommended action
   (`request-revision` / `comment-label` / `close-PR` / `approve`).

## Rules
- Static scanner first, LLM judgment second — never skip the scanner.
- Advisory output only; never treat the verdict as an automatic merge block.
- If the diff is empty, say "no changes to scan" and stop.
