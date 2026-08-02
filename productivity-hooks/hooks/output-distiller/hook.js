#!/usr/bin/env node
/**
 * Output Distiller — PostToolUse hook processor
 * Reads JSON from stdin, distills Bash output, outputs hook-specific JSON.
 *
 * Input: JSON from OpenClaude hook (via stdin)
 * Output: JSON with hookSpecificOutput.updatedToolOutput (via stdout)
 *
 * Exit 0 with JSON output = replace tool output
 * Exit 0 with no output = pass through unchanged
 */

const { distill } = require('./distiller.js');

let inputData = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { inputData += chunk; });
process.stdin.on('end', () => {
  try {
    const hookData = JSON.parse(inputData);

    // Only process Bash tool calls
    if (hookData.tool_name !== 'Bash') {
      process.exit(0);
    }

    // Extract command and output
    const command = hookData.command || '';
    const output = hookData.tool_result?.output || hookData.output || '';

    if (!output) {
      process.exit(0);
    }

    // Run distiller with command auto-detection
    const result = distill(output, { command });

    if (!result.distilled) {
      // No distillation needed, pass through
      process.exit(0);
    }

    // Output hook-specific JSON format to replace tool output
    const banner = `🎧 [output-distiller: collapsed ${result.originalLines - result.outputLines} noise line${result.originalLines - result.outputLines === 1 ? '' : 's'} (${result.originalLines}→${result.outputLines})]`;
    const updatedOutput = `${banner}\n${result.text}`;

    const response = {
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        updatedToolOutput: updatedOutput
      }
    };

    process.stdout.write(JSON.stringify(response));
    process.exit(0);
  } catch (err) {
    // FAIL OPEN — any error = pass through original
    process.exit(0);
  }
});
