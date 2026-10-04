# pr-slop-guard

OpenClaude plugin for PR slop detection — catches AI-generated low-quality code before a PR is opened.

## What it does

Two-layer scan over a git diff:

1. **Static scan** (`skills/slop-scan/scripts/slop_scan.py`, zero LLM cost, seconds): AST + regex detectors for 8 statically-detectable slop rules — try-except blankets, swallowed exceptions, read-modify-write races, broad auth-or, unused imports, function-level imports, mock-testing-mock, env-var cargo cult.
2. **LLM judgment** (skill procedure): semantic confirmation of context-dependent findings — hallucinated APIs, fake tests, over-abstraction. Emits verdict **SLOP / SUSPECT / CLEAN** + P1/P2/P3 table + one recommended action.

Semantics mirror CodeRabbit slop detection: advisory only, never a merge block; exempt collaborators/owners/bots; target external low-quality contributions.

## Layout

```
pr-slop-guard/
├── .claude-plugin/plugin.json
├── skills/slop-scan/SKILL.md            # trigger phrases + 4-step procedure
│   ├── references/patterns.md           # 12 Potapov patterns (P1/P2/P3)
│   └── scripts/slop_scan.py             # static scanner (stdin or --diff-file)
└── commands/slop-check.md               # /slop-check [--staged|<ref>]
```

## Usage

```
/slop-check            # diff main...HEAD
/slop-check --staged   # staged changes (pre-PR local check)
/slop-check develop    # diff against another base
```

Or invoke the skill directly: "check this PR for slop", "is this diff AI slop".

Direct script use (no LLM):

```bash
git diff main...HEAD | python skills/slop-scan/scripts/slop_scan.py
python skills/slop-scan/scripts/slop_scan.py --diff-file /tmp/pr.diff --min-severity P1
```

## Verdict logic

| Static result | Verdict |
|---|---|
| 2+ P1 | SLOP |
| 1 P1, or 3+ P2 | SUSPECT |
| P2 only (< 3) | SUSPECT |
| nothing | CLEAN |

Recommended action: `request-revision` (any P1) · `comment-label` (2+ P1 or first-time external author) · `close-PR` (P1 ≥ 3, no tests) · `approve` (CLEAN).

## References

- CodeRabbit slop detection docs — label-based, first-full-review-only, exempt collaborators.
- Potapov, "Detecting AI Slop: A Code Review Checklist" (June 2026) — 12 patterns P1/P2/P3.
- Empirics: CodeRabbit (470 repos, 1.7× issues in AI-assisted PRs), Veracode (45% AI samples with security flaws).
