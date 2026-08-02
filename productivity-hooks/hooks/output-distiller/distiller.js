/**
 * Output Distiller — Core algorithm
 * Ported from pi-output-distiller/distiller.ts
 *
 * Collapses noisy command output (progress bars, ANSI churn, install spam)
 * while preserving every error/warning/failure line.
 */

const DEFAULT_MIN_LINES = 40;
const ANSI_RE = /\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;

function stripAnsi(text) {
  return text.replace(ANSI_RE, '');
}

function collapseCarriageReturns(text) {
  return text
    .split('\n')
    .map((line) => {
      if (line.indexOf('\r') === -1) return line;
      const parts = line.split('\r');
      return parts[parts.length - 1];
    })
    .join('\n');
}

const NOISE_LINE_PATTERNS = [
  /^\s*$/,
  /^[\s#=\-.>▓░█▁▂▃▄▅▆▇■●○◐◓◑◒|/\\]+$/,
  /[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣾⣽⣻⢿⡿⣟⣯⣷]/,
  /⸨[░▒▓█\\s]*⸩/,
  /^\s*\[?=*>?\s*\]?\s*\d{1,3}%/,
  /^\s*\d{1,3}%\s*(?:\||complete|done)?\s*$/i,
  /^\s*(?:downloading|downloaded|fetching|fetched|resolving|resolved|extracting|unpacking|reading|writing|linking)\b.*$/i,
  /^\s*(?:compiling|building|preparing|installing)\s+[\w@./+-]+(?:\s+v?[\d.]+)?\s*$/i,
  /\breify(?:Node)?:|\btiming\s+reify/i,
  /^\s*added\s+(?:dependency|package)\s+\S/i,
  /^\s*(?:\d+\/\d+)\s+\S.*$/,
];

const KEEP_LINE_PATTERNS = [
  /\berror\b/i,
  /\berr!?\b/i,
  /\bwarn(?:ing)?\b/i,
  /\bfail(?:ed|ure)?\b/i,
  /\bpanic\b/i,
  /\bfatal\b/i,
  /\bexception\b/i,
  /\btraceback\b/i,
  /\bassert(?:ion)?\b/i,
  /\bcannot\b|\bunable to\b|\bnot found\b|\bmissing\b|\bunexpected\b/i,
  /\bdenied\b|\bunauthorized\b|\bforbidden\b|\btimed? ?out\b/i,
  /\bconflict\b|\bunresolved\b|\bincompatible\b/i,
  /^\s*at\s+.+\(.+:\d+:\d+\)\s*$/,
  /^\s*File ".*", line \d+/,
  /\bexit(?:ed)? (?:code|status)\b/i,
  /(?<!\w)[Ee]:\s|\bE\d{3,}\b/,
];

const TOOL_PATTERNS = {
  jest: [
    /Test Suites:\s+\d+ passed/i,
    /Tests:\s+\d+ passed/i,
    /Snapshots:\s+\d+/i,
    /Time:\s+[\d.]+ s/i,
    /Ran all test suites/i,
  ],
  cargo: [
    /test result:.*\d+ passed/i,
    /Finished.*target/i,
    /running \d+ tests/i,
  ],
  docker: [
    /Building.*FINISHED/i,
    /naming to/i,
    /exporting to image/i,
  ],
  python: [
    /Traceback/i,
    /File ".*", line \d+/i,
    /\w+Error:/i,
  ],
  npm: [
    /added \d+ packages/i,
    /audited \d+ packages/i,
    /vulnerabilities/i,
    /found \d+ (?:moderate|high|low|critical)/i,
  ],
};

function isNoiseLine(line) {
  for (const k of KEEP_LINE_PATTERNS) if (k.test(line)) return false;
  for (const n of NOISE_LINE_PATTERNS) if (n.test(line)) return true;
  return false;
}

function hasKeepSignal(line) {
  for (const k of KEEP_LINE_PATTERNS) if (k.test(line)) return true;
  return false;
}

function normalizeForDedup(line) {
  return line.replace(/\s+/g, ' ').trim();
}

function detectToolFromCommand(command) {
  const cmd = command.toLowerCase();
  if (cmd.includes('npm') || cmd.includes('pnpm') || cmd.includes('yarn')) return 'npm';
  if (cmd.includes('cargo')) return 'cargo';
  if (cmd.includes('docker')) return 'docker';
  if (cmd.includes('jest') || cmd.includes('vitest')) return 'jest';
  if (cmd.includes('python') || cmd.includes('pytest')) return 'python';
  return undefined;
}

function matchesToolPattern(line, tool) {
  const patterns = TOOL_PATTERNS[tool];
  if (!patterns) return false;
  return patterns.some((p) => p.test(line));
}

function matchesCustomRule(line, rules) {
  for (const rule of rules) {
    try {
      const regex = new RegExp(rule.pattern, 'i');
      if (regex.test(line)) {
        return rule.action;
      }
    } catch {
      // Invalid regex, skip
    }
  }
  return null;
}

function distill(raw, options = {}) {
  const minLines = options.minLines ?? DEFAULT_MIN_LINES;
  let tool = options.tool;
  const customRules = options.customRules || [];

  if (!tool && options.command) {
    tool = detectToolFromCommand(options.command);
  }

  const noResult = (rule, lines) => ({
    text: raw,
    distilled: false,
    rule,
    originalLines: lines,
    outputLines: lines,
    tool,
  });

  if (typeof raw !== 'string' || raw.length === 0) return noResult('empty', 0);

  const cleaned = collapseCarriageReturns(stripAnsi(raw));
  const lines = cleaned.split('\n');
  const originalLines = lines.length;

  if (originalLines < minLines) return noResult('below-min-lines', originalLines);

  const keep = new Array(lines.length).fill(false);
  let keepSignalCount = 0;
  let noiseCount = 0;

  const dupCounts = new Map();
  for (let i = 0; i < lines.length; i++) {
    if (hasKeepSignal(lines[i]) || isNoiseLine(lines[i])) continue;
    if (tool && matchesToolPattern(lines[i], tool)) continue;
    if (matchesCustomRule(lines[i], customRules) !== null) continue;
    const key = normalizeForDedup(lines[i]);
    if (key.length === 0) continue;
    dupCounts.set(key, (dupCounts.get(key) ?? 0) + 1);
  }
  const DUP_THRESHOLD = 20;
  const dupSeen = new Map();

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const customRuleResult = matchesCustomRule(line, customRules);

    if (customRuleResult === 'keep') {
      keep[i] = true;
      keepSignalCount++;
    } else if (customRuleResult === 'drop') {
      noiseCount++;
    } else if (tool && matchesToolPattern(line, tool)) {
      keep[i] = true;
      keepSignalCount++;
    } else if (hasKeepSignal(line)) {
      keep[i] = true;
      keepSignalCount++;
    } else if (isNoiseLine(line)) {
      noiseCount++;
    } else {
      const key = normalizeForDedup(line);
      const total = dupCounts.get(key) ?? 0;
      if (total > DUP_THRESHOLD) {
        const seen = (dupSeen.get(key) ?? 0) + 1;
        dupSeen.set(key, seen);
        if (seen === 1) {
          keep[i] = true;
        } else {
          noiseCount++;
        }
      } else {
        keep[i] = true;
      }
    }
  }

  if (noiseCount / originalLines < 0.25) {
    return noResult('insufficient-noise', originalLines);
  }

  const HEAD = 3;
  const TAIL = 5;
  for (let i = 0; i < Math.min(HEAD, lines.length); i++) {
    if (matchesCustomRule(lines[i], customRules) === 'drop') continue;
    keep[i] = true;
  }
  for (let i = Math.max(0, lines.length - TAIL); i < lines.length; i++) {
    if (matchesCustomRule(lines[i], customRules) === 'drop') continue;
    keep[i] = true;
  }

  for (let i = 0; i < lines.length; i++) {
    if (keep[i] && keepSignalCount > 0 && hasKeepSignal(lines[i])) {
      if (i > 0) keep[i - 1] = true;
      if (i < lines.length - 1) keep[i + 1] = true;
    }
  }

  const out = [];
  let dropRun = 0;
  for (let i = 0; i < lines.length; i++) {
    if (keep[i]) {
      if (dropRun > 0) {
        out.push(`  … [${dropRun} noise line${dropRun === 1 ? '' : 's'} collapsed] …`);
        dropRun = 0;
      }
      out.push(lines[i]);
    } else {
      dropRun++;
    }
  }
  if (dropRun > 0) {
    out.push(`  … [${dropRun} noise line${dropRun === 1 ? '' : 's'} collapsed] …`);
  }

  const outputLines = out.length;

  if (outputLines >= originalLines * 0.9) {
    return noResult('marginal-gain', originalLines);
  }

  return {
    text: out.join('\n'),
    distilled: true,
    rule: keepSignalCount > 0 ? 'distilled-with-signal' : 'distilled-noise-only',
    originalLines,
    outputLines,
    tool,
  };
}

module.exports = {
  distill,
  stripAnsi,
  collapseCarriageReturns,
  isNoiseLine,
  hasKeepSignal,
  normalizeForDedup,
  detectToolFromCommand,
  matchesToolPattern,
  matchesCustomRule,
};
