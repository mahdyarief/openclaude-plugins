/**
 * ADHD Mode — Core module
 *
 * Port of pi-adhd-mode extension to OpenClaude hook system.
 * Detection heuristics for ADHD-friendly output rules.
 */

// ── ADHD System Prompt Rules ──────────────────────────────────────────────

const ADHD_SYSTEM_PROMPT = `
## ADHD-Friendly Output Mode (ACTIVE)

The reader has ADHD. Shape every response accordingly.

### Five Principles
1. Working memory is small. Don't ask reader to "keep in mind X."
2. Knowing ≠ doing. Bridge understanding to action.
3. Starting is hardest. First action must be obvious, small, doable now.
4. Time estimates feel uniform. Give specific estimates, not vague ones.
5. Dopamine is scarce. Make wins visible.

### Rules
- **Lead with next action.** First line = what to do now.
- **Number multi-step work.** Not bullets. Numbers.
- **Restate state across turns.** What we're doing, what happened, what's next.
- **Suppress tangents.** No "by the way", no sidebars.
- **Give specific time estimates.** "3 minutes" not "a bit of work".
- **Make wins visible.** "✓ Build succeeded" not "exit code 0".
- **Delete the wrapper.** No announcing sentences, no "anything else?" recaps, no hedging adverbs, no idioms.
- **Preserve tool output verbatim.** Don't compress, summarize, or elide file/command output.

### Pre-Send Check
Before sending, verify: if reader reads only first line + last line, do they know (a) what to do next, and (b) what just happened?
`;

// ── Detection Heuristics ──────────────────────────────────────────────────

const TANGENT_PATTERNS = [
  /by the way/i,
  /you might also (want to|consider|like)/i,
  /as a side note/i,
  /on a related note/i,
  /related(?:ly)?[,:]\s/i,
  /it'?s worth (noting|mentioning)/i,
  /before (we continue|i forget)/i,
];

const ANNOUNCEMENT_PATTERNS = [
  /^i('ll| will) (help you|show you|explain|walk you through|create|build|make|generate)/im,
  /^let me (show|explain|walk|help|create|build|check|verify)/im,
  /^in this (response|answer|explanation)/im,
  /^to answer your question/im,
  /^great question/im,
  /^certainly[!,]/im,
  /^of course[!,]/im,
  /^absolutely[!,]/im,
  /^sure[!,]/im,
];

const WIN_PATTERNS = [
  /✓|✅|✔|success|succeeded|passed|complete|done|working|fixed|resolved/i,
];

const TIME_ESTIMATE_PATTERNS = [
  /\d+\s*(second|minute|hour|day)s?/i,
  /\d+:\d+/,
  /about \d+/i,
  /~\d+/i,
  /roughly \d+/i,
];

// ── Detection Functions ───────────────────────────────────────────────────

function countTangents(text) {
  return TANGENT_PATTERNS.filter((p) => p.test(text)).length;
}

function hasNumberedSteps(text) {
  return /^\s*\d+\.\s/m.test(text);
}

function hasTimeEstimate(text) {
  return TIME_ESTIMATE_PATTERNS.some((p) => p.test(text));
}

function hasVisibleWin(text) {
  return WIN_PATTERNS.some((p) => p.test(text));
}

function startsWithAction(text) {
  const firstLine = text.split('\n')[0]?.trim() ?? '';
  if (!firstLine) return false;
  return !ANNOUNCEMENT_PATTERNS.some((p) => p.test(firstLine));
}

function hasWrapper(text) {
  // Detect trailing "anything else?" or similar recaps
  const lastLines = text.trim().split('\n').slice(-3).join('\n');
  return /anything\s+else|let me know if|feel free to ask/i.test(lastLines);
}

// ── Analysis ──────────────────────────────────────────────────────────────

function analyze(text) {
  const issues = [];

  if (!startsWithAction(text)) {
    issues.push('❌ Does NOT start with action — first line is an announcement/wrapper.');
  }

  const tangents = countTangents(text);
  if (tangents > 0) {
    issues.push(`❌ Contains ${tangents} tangent(s) ("by the way", side notes, etc.).`);
  }

  if (!hasNumberedSteps(text) && text.split('\n').length > 3) {
    issues.push('⚠️  No numbered steps found — use 1. 2. 3. for multi-step work.');
  }

  if (!hasTimeEstimate(text)) {
    issues.push('⚠️  No time estimate found — add specific estimates ("3 minutes").');
  }

  if (!hasVisibleWin(text)) {
    issues.push('⚠️  No visible win found — mark wins with ✓ or "succeeded".');
  }

  if (hasWrapper(text)) {
    issues.push('❌ Contains wrapper/recap ("anything else?", "let me know if...").');
  }

  return {
    issues,
    pass: issues.length === 0,
    tangentCount: tangents,
    hasNumberedSteps: hasNumberedSteps(text),
    hasTimeEstimate: hasTimeEstimate(text),
    hasVisibleWin: hasVisibleWin(text),
    startsWithAction: startsWithAction(text),
    stats: {
      tangentsSuppressed: tangents > 0 ? tangents : 0,
      stepsNumbered: hasNumberedSteps(text) ? 1 : 0,
      timeEstimatesGiven: hasTimeEstimate(text) ? 1 : 0,
      winsMadeVisible: hasVisibleWin(text) ? 1 : 0,
      preSendChecksPassed: startsWithAction(text) ? 1 : 0,
    },
  };
}

// ── Reminder Banner ───────────────────────────────────────────────────────

function buildReminderBanner(command) {
  const lines = [
    '╔══════════════════════════════════════════════════════╗',
    '║  🧠 ADHD MODE ACTIVE                                ║',
    '║                                                     ║',
    '║  Rules for your next response:                      ║',
    '║  1. Lead with action — what to do NOW               ║',
    '║  2. Number steps — not bullets                      ║',
    '║  3. Restate state — what/doing/happened/next         ║',
    '║  4. Suppress tangents — no "by the way"             ║',
    '║  5. Give estimates — "3 min" not "soon"             ║',
    '║  6. Make wins visible — ✓ not "exit code 0"         ║',
    '║  7. Delete wrapper — no announcing, no recap        ║',
    '║  8. Preserve tool output — verbatim                 ║',
    '╚══════════════════════════════════════════════════════╝',
  ];
  return lines.join('\n');
}

// ── Stats Persistence ─────────────────────────────────────────────────────

const fs = require('fs');
const path = require('path');

const STATS_FILE = path.join(__dirname, 'adhd-stats.json');

function loadStats() {
  try {
    if (fs.existsSync(STATS_FILE)) {
      return JSON.parse(fs.readFileSync(STATS_FILE, 'utf8'));
    }
  } catch {
    // Corrupted file, reset
  }
  return {
    sessionStart: Date.now(),
    responsesShaped: 0,
    tangentsSuppressed: 0,
    stepsNumbered: 0,
    timeEstimatesGiven: 0,
    winsMadeVisible: 0,
    preSendChecksPassed: 0,
  };
}

function saveStats(stats) {
  try {
    fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2), 'utf8');
  } catch {
    // Best-effort
  }
}

function getStatsSummary() {
  const stats = loadStats();
  const elapsed = Math.round((Date.now() - stats.sessionStart) / 60000);
  return [
    `📊 ADHD mode stats (${elapsed}m session)`,
    `  responses shaped: ${stats.responsesShaped}`,
    `  steps numbered: ${stats.stepsNumbered}`,
    `  time estimates: ${stats.timeEstimatesGiven}`,
    `  tangents suppressed: ${stats.tangentsSuppressed}`,
    `  wins made visible: ${stats.winsMadeVisible}`,
    `  pre-send checks passed: ${stats.preSendChecksPassed}`,
  ].join('\n');
}

function resetStats() {
  const stats = {
    sessionStart: Date.now(),
    responsesShaped: 0,
    tangentsSuppressed: 0,
    stepsNumbered: 0,
    timeEstimatesGiven: 0,
    winsMadeVisible: 0,
    preSendChecksPassed: 0,
  };
  saveStats(stats);
  return stats;
}

module.exports = {
  ADHD_SYSTEM_PROMPT,
  TANGENT_PATTERNS,
  ANNOUNCEMENT_PATTERNS,
  WIN_PATTERNS,
  TIME_ESTIMATE_PATTERNS,
  countTangents,
  hasNumberedSteps,
  hasTimeEstimate,
  hasVisibleWin,
  startsWithAction,
  hasWrapper,
  analyze,
  buildReminderBanner,
  loadStats,
  saveStats,
  getStatsSummary,
  resetStats,
};
