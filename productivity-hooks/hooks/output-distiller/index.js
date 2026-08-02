#!/usr/bin/env node
/**
 * Output Distiller — CLI Entry Point
 *
 * Reads tool output from stdin (or as argument), runs distillation,
 * and outputs the result to stdout.
 *
 * Usage:
 *   echo "noisy output" | node index.js
 *   node index.js --file output.txt
 *   node index.js --command "npm install"
 *
 * Returns the distilled output to stdout.
 * Exit code 0 = distilled, 1 = error, 2 = no distillation needed.
 */

const { distill } = require('./distiller.js');
const fs = require('fs');

let input = '';
let command = '';
let tool = '';
let minLines = undefined;

// Parse arguments
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--file' && args[i + 1]) {
    input = fs.readFileSync(args[i + 1], 'utf8');
    i++;
  } else if (args[i] === '--command' && args[i + 1]) {
    command = args[i + 1];
    i++;
  } else if (args[i] === '--tool' && args[i + 1]) {
    tool = args[i + 1];
    i++;
  } else if (args[i] === '--min-lines' && args[i + 1]) {
    minLines = parseInt(args[i + 1], 10);
    i++;
  } else if (args[i] === '--help' || args[i] === '-h') {
    console.log(`
Output Distiller — Noise-canceling for bash command output

Usage:
  echo "noisy output" | node index.js
  node index.js --file output.txt
  node index.js --command "npm install"

Options:
  --file <path>       Read input from file
  --command <cmd>     Auto-detect tool from command
  --tool <name>       Force tool type (jest, cargo, docker, python, npm)
  --min-lines <n>     Minimum lines before distillation (default: 40)
  --help, -h          Show this help

Output:
  Distilled text to stdout
  Exit code 0 = distilled, 1 = error, 2 = no distillation needed
`);
    process.exit(0);
  }
}

// Read from stdin if no file provided
if (!input) {
  input = fs.readFileSync(0, 'utf8');
}

if (!input || input.length === 0) {
  console.error('Error: No input provided');
  process.exit(1);
}

try {
  const result = distill(input, { command, tool, minLines });

  if (!result.distilled) {
    // No distillation needed, output original
    console.error(`[distiller] No distillation: ${result.rule} (${result.originalLines} lines)`);
    process.exit(2);
  }

  // Output distilled result
  const saved = result.originalLines - result.outputLines;
  const banner = `🎧 [output-distiller: collapsed ${saved} noise line${saved === 1 ? '' : 's'} (${result.originalLines}→${result.outputLines}). Toggle: "distiller off"]`;
  console.log(`${banner}\n${result.text}`);
  process.exit(0);
} catch (err) {
  // FAIL OPEN — never break a tool result
  console.error(`[distiller] Error: ${err.message}`);
  process.exit(1);
}
