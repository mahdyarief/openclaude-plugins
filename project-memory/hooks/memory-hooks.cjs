#!/usr/bin/env node
'use strict';

/**
 * SessionStart hook for project-memory.
 *
 * The upstream MCP server (uvx project-mem-mcp) only READS MEMORY.md and raises
 * FileNotFoundError when it is absent — nothing ever creates the file. This hook
 * makes the first session in a project bootstrap it so the MCP tools work.
 *
 * Rules:
 *  - Only act on directories that look like a project (marker file present).
 *  - Never create the file in the user's home directory.
 *  - Opt out with PROJECT_MEMORY_AUTOCREATE=0.
 *  - Emit a small digest (title + headings), never the whole file, so the
 *    context cost stays bounded; the model fetches content via the MCP tools.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const FILE = 'MEMORY.md';
const MAX_HEADINGS = 12;
const MARKERS = [
  '.git', '.trail', '.claude', '.openclaude',
  'CLAUDE.md', 'AGENTS.md',
  'package.json', 'pyproject.toml', 'Cargo.toml', 'go.mod',
  'pom.xml', 'build.gradle', 'composer.json', 'Gemfile',
];

function projectRoot() {
  if (process.env.CLAUDE_PROJECT_DIR) return path.resolve(process.env.CLAUDE_PROJECT_DIR);
  return path.resolve(process.cwd());
}

function isProject(dir) {
  return MARKERS.some((m) => fs.existsSync(path.join(dir, m)));
}

function isHome(dir) {
  const home = path.resolve(os.homedir());
  return dir.toLowerCase() === home.toLowerCase();
}

function template(dir) {
  const name = path.basename(dir);
  const today = new Date().toISOString().slice(0, 10);
  return [
    `# Project Memory — ${name}`,
    '',
    '> Auto-created on first session. Keep this current through the project-memory',
    '> MCP tools (set_project_memory / update_project_memory) — not with Write/Edit.',
    '',
    '## Architecture & Why',
    '',
    '- (decisions plus the reason behind them)',
    '',
    '## Conventions',
    '',
    '- (non-obvious rules a newcomer could not infer from the code)',
    '',
    '## Gotchas',
    '',
    '- (surprises that cost real debugging time)',
    '',
    '## Key files',
    '',
    '- `path/to/file` — purpose',
    '',
    '## Recent Sessions',
    '',
    `- ${today}: Project memory created.`,
    '',
  ].join('\n');
}

function digest(content) {
  const lines = content.split('\n');
  const headings = [];
  for (const line of lines) {
    const m = line.match(/^(#{1,3})\s+(.+?)\s*$/);
    if (m) headings.push(`${m[1]} ${m[2]}`);
    if (headings.length >= MAX_HEADINGS) break;
  }
  const bytes = Buffer.byteLength(content, 'utf8');
  return { lineCount: lines.length, bytes, headings };
}

function emit(event, context) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: event, additionalContext: context },
  }));
}

function main() {
  const event = process.argv[2] || 'session-start';
  if (event !== 'session-start') return;

  const dir = projectRoot();
  const file = path.join(dir, FILE);
  const exists = fs.existsSync(file);

  if (!exists) {
    if (process.env.PROJECT_MEMORY_AUTOCREATE === '0') return;
    if (isHome(dir) || !isProject(dir)) return;
    try {
      fs.writeFileSync(file, template(dir), { flag: 'wx', encoding: 'utf8' });
    } catch {
      return;
    }
  }

  let content = '';
  try {
    content = fs.readFileSync(file, 'utf8');
  } catch {
    return;
  }

  if (!exists) {
    emit(event,
      `project-memory: created ${file} because it did not exist. ` +
      `Populate it with set_project_memory or update_project_memory; never write it directly with Write/Edit.`);
    return;
  }

  const d = digest(content);
  const toc = d.headings.length ? ` Sections: ${d.headings.join(' | ')}.` : '';
  emit(event,
    `project-memory: ${file} exists (${d.lineCount} lines, ${d.bytes} bytes).${toc} ` +
    `Read it with get_project_memory(project_path=${JSON.stringify(dir)}) before making decisions; ` +
    `update via update_project_memory, not Write/Edit.`);
}

main();
