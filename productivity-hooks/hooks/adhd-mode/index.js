#!/usr/bin/env node
/**
 * ADHD Mode — CLI entry point
 *
 * Manual usage:
 *   echo "some output" | node index.js
 *   node index.js --file output.txt
 *   node index.js --command "npm install"
 *   node index.js --analyze "some response text"
 *   node index.js --stats
 *   node index.js --reset-stats
 */

const { analyze, buildReminderBanner, getStatsSummary, resetStats } = require('./adhd.js');

function main() {
  const args = process.argv.slice(2);

  if (args.includes('--stats')) {
    console.log(getStatsSummary());
    process.exit(0);
  }

  if (args.includes('--reset-stats')) {
    const stats = resetStats();
    console.log('✓ ADHD mode stats reset.');
    process.exit(0);
  }

  if (args.includes('--analyze')) {
    const idx = args.indexOf('--analyze');
    const text = args[idx + 1];
    if (!text) {
      console.error('Usage: node index.js --analyze "response text"');
      process.exit(1);
    }
    const result = analyze(text);
    if (result.pass) {
      console.log('✅ All ADHD checks passed.');
    } else {
      console.log('⚠️  ADHD issues found:');
      result.issues.forEach((i) => console.log(`  ${i}`));
    }
    process.exit(0);
  }

  // File mode
  const fileIdx = args.indexOf('--file');
  if (fileIdx !== -1) {
    const filePath = args[fileIdx + 1];
    if (!filePath) {
      console.error('Usage: node index.js --file output.txt');
      process.exit(1);
    }
    const fs = require('fs');
    const content = fs.readFileSync(filePath, 'utf8');

    const commandIdx = args.indexOf('--command');
    const command = commandIdx !== -1 ? args[commandIdx + 1] : '';
    const banner = buildReminderBanner(command || '');
    console.log(banner);
    console.log(content);
    process.exit(0);
  }

  // Stdin mode (pipe)
  let inputData = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => { inputData += chunk; });
  process.stdin.on('end', () => {
    const commandIdx = args.indexOf('--command');
    const command = commandIdx !== -1 ? args[commandIdx + 1] : '';
    const banner = buildReminderBanner(command || '');
    console.log(banner);
    console.log(inputData);
  });
}

main();
