#!/usr/bin/env node
/**
 * ADHD Mode — PostToolUse hook processor
 *
 * Reads JSON from stdin (OpenClaude hook format), processes output through
 * ADHD detection heuristics, and prepends a reminder banner after Bash commands
 * so the model is reminded of ADHD rules before generating its next response.
 *
 * Input: JSON from OpenClaude hook (via stdin)
 * Output: JSON with hookSpecificOutput.updatedToolOutput (via stdout)
 *
 * Exit 0 with JSON output = replace tool output
 * Exit 0 with no output = pass through unchanged
 */

const { analyze, buildReminderBanner, loadStats, saveStats, getStatsSummary } = require('./adhd.js');
const fs = require('fs');
const path = require('path');

const CONFIG_FILE = path.join(__dirname, 'config.json');

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    }
  } catch {
    // Fall through to defaults
  }
  return { enabled: true, rules: [], skipCommands: [] };
}

let inputData = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { inputData += chunk; });
process.stdin.on('end', () => {
  try {
    const config = loadConfig();

    if (!config.enabled) {
      process.exit(0);
    }

    const hookData = JSON.parse(inputData);

    // Only process Bash tool calls
    if (hookData.tool_name !== 'Bash') {
      process.exit(0);
    }

    const command = hookData.command || '';
    const output = hookData.tool_result?.output || hookData.output || '';

    // Skip commands that produce no meaningful output
    const cmdName = command.split(' ')[0]?.toLowerCase() || '';
    const skipCommands = config.skipCommands || ['cat', 'type', 'head', 'tail', 'bat', 'less', 'more', 'nano', 'vim', 'code'];
    if (skipCommands.includes(cmdName)) {
      process.exit(0);
    }

    if (!output) {
      process.exit(0);
    }

    // Analyze the command output for ADHD rule compliance context
    // We prepend a reminder banner so the model sees it before responding
    const banner = buildReminderBanner(command);
    const updatedOutput = `${banner}\n${output}`;

    // Track stats
    try {
      const stats = loadStats();
      stats.responsesShaped++;
      saveStats(stats);
    } catch {
      // Best-effort
    }

    const response = {
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        updatedToolOutput: updatedOutput,
      },
    };

    process.stdout.write(JSON.stringify(response));
    process.exit(0);
  } catch (err) {
    // FAIL OPEN — any error = pass through original
    process.exit(0);
  }
});
