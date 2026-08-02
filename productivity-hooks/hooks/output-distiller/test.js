#!/usr/bin/env node
/**
 * Output Distiller — Automated Test Suite
 * Runs all test cases and reports pass/fail.
 */

const { distill, stripAnsi, collapseCarriageReturns, isNoiseLine, hasKeepSignal, normalizeForDedup, detectToolFromCommand } = require('./distiller.js');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const HOOK_JS = path.join(__dirname, 'hook.js');
const INDEX_JS = path.join(__dirname, 'index.js');

let passed = 0;
let failed = 0;
let total = 0;

function assert(name, condition, detail) {
  total++;
  if (condition) {
    passed++;
    console.log(`  ✓ ${name}`);
  } else {
    failed++;
    console.log(`  ✗ ${name}${detail ? ': ' + detail : ''}`);
  }
}

// ─── Test 1: Basic noise detection ───
console.log('\n=== Test 1: Noise line detection ===');
assert('empty line is noise', isNoiseLine(''));
assert('whitespace is noise', isNoiseLine('   '));
assert('progress bar is noise', isNoiseLine('▓▓▓▓▓▓▓░░░░░'));
assert('spinner is noise', isNoiseLine('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'));
assert('downloading is noise', isNoiseLine('Downloading package...'));
assert('installing is noise', isNoiseLine('Installing express@4.18.0'));
assert('error is NOT noise', !isNoiseLine('error: ENOENT'));
assert('warning is NOT noise', !isNoiseLine('warn: something'));
assert('reify line is noise', isNoiseLine('  reify Node: timing reify:123'));

// ─── Test 2: Keep signal detection ───
console.log('\n=== Test 2: Keep signal detection ===');
assert('error detected', hasKeepSignal('error: file not found'));
assert('warn detected', hasKeepSignal('warn: deprecated API'));
assert('fail detected', hasKeepSignal('build failed'));
assert('panic detected', hasKeepSignal('panic: runtime error'));
assert('fatal detected', hasKeepSignal('fatal error'));
assert('traceback detected', hasKeepSignal('Traceback (most recent call last):'));
assert('cannot detected', hasKeepSignal('cannot resolve module'));
assert('reify line has NO keep signal', !hasKeepSignal('  reify Node: timing reify:123'));
assert('normal line has NO keep signal', !hasKeepSignal('  added 100 packages'));

// ─── Test 3: Reify false positive fix ───
console.log('\n=== Test 3: Reify false positive fix ===');
const reifyLine = '  reify Node: timing reify:';
assert('reify does not match [Ee]:', !hasKeepSignal(reifyLine));
assert('reify matches noise', isNoiseLine(reifyLine));

// ─── Test 4: Tool detection ───
console.log('\n=== Test 4: Tool detection ===');
assert('npm detected', detectToolFromCommand('npm install express') === 'npm');
assert('cargo detected', detectToolFromCommand('cargo build') === 'cargo');
assert('docker detected', detectToolFromCommand('docker build .') === 'docker');
assert('jest detected', detectToolFromCommand('npx jest') === 'jest');
assert('python detected', detectToolFromCommand('python test.py') === 'python');
assert('unknown returns undefined', detectToolFromCommand('ls -la') === undefined);

// ─── Test 5: Normalize for dedup ───
console.log('\n=== Test 5: Normalize for dedup ===');
assert('collapses whitespace', normalizeForDedup('  hello   world  ') === 'hello world');
assert('trims', normalizeForDedup('  trimmed  ') === 'trimmed');

// ─── Test 6: ANSI stripping ───
console.log('\n=== Test 6: ANSI stripping ===');
assert('strips color codes', stripAnsi('\x1b[31mred text\x1b[0m') === 'red text');
assert('handles no ANSI', stripAnsi('plain text') === 'plain text');

// ─── Test 7: Carriage return collapse ───
console.log('\n=== Test 7: Carriage return collapse ===');
assert('collapses CR', collapseCarriageReturns('old\rnew') === 'new');
assert('handles multiple CR', collapseCarriageReturns('a\rb\rnew') === 'new');

// ─── Test 8: Distill — below min lines (pass-through) ───
console.log('\n=== Test 8: Distill — below min lines ===');
const shortResult = distill('hello\nworld');
assert('short output not distilled', !shortResult.distilled);
assert('short rule is below-min-lines', shortResult.rule === 'below-min-lines');

// ─── Test 9: Distill — insufficient noise (pass-through) ───
console.log('\n=== Test 9: Distill — insufficient noise ===');
const cleanLines = [];
for (let i = 0; i < 50; i++) cleanLines.push(`meaningful line ${i}`);
const cleanResult = distill(cleanLines.join('\n'));
assert('clean output not distilled', !cleanResult.distilled);
assert('clean rule is insufficient-noise', cleanResult.rule === 'insufficient-noise');

// ─── Test 10: Distill — actual noise with error ───
console.log('\n=== Test 10: Distill — noise with error signal ===');
const noisyLines = [];
for (let i = 0; i < 45; i++) noisyLines.push('  reify Node: timing reify:' + i);
noisyLines.push('  error: ENOENT no such file or directory');
for (let i = 0; i < 10; i++) noisyLines.push('  added ' + i + ' packages');
const noisyResult = distill(noisyLines.join('\n'), { command: 'npm install' });
assert('noisy output is distilled', noisyResult.distilled);
assert('has signal preserved', noisyResult.rule === 'distilled-with-signal');
assert('output is shorter', noisyResult.outputLines < noisyResult.originalLines);
assert('error line in output', noisyResult.text.includes('error: ENOENT'));
assert('has noise collapsed marker', noisyResult.text.includes('noise line'));

// ─── Test 11: Distill — npm tool detection ───
console.log('\n=== Test 11: Distill — npm tool detection ===');
const npmLines = [];
for (let i = 0; i < 30; i++) npmLines.push('  reify:timing reify ' + i);
npmLines.push('  added 150 packages in 3.2s');
npmLines.push('  audited 200 packages in 0.5s');
for (let i = 0; i < 20; i++) npmLines.push('  reify:extract ' + i);
const npmResult = distill(npmLines.join('\n'), { command: 'npm install express' });
assert('npm tool detected', npmResult.tool === 'npm');
assert('npm output distilled', npmResult.distilled);

// ─── Test 12: Hook processor — non-Bash tool (pass-through) ───
console.log('\n=== Test 12: Hook processor — non-Bash tool ===');
try {
  const hookInput = JSON.stringify({ tool_name: 'Read', output: 'some output' });
  const hookResult = execSync(`node "${HOOK_JS}"`, { input: hookInput, encoding: 'utf8', timeout: 5000 });
  assert('non-Bash produces no output', hookResult.trim() === '');
} catch (e) {
  assert('non-Bash hook did not crash', false, e.message);
}

// ─── Test 13: Hook processor — clean Bash output (pass-through) ───
console.log('\n=== Test 13: Hook processor — clean Bash output ===');
try {
  const hookInput = JSON.stringify({ tool_name: 'Bash', command: 'ls', output: 'file1.txt\nfile2.txt' });
  const hookResult = execSync(`node "${HOOK_JS}"`, { input: hookInput, encoding: 'utf8', timeout: 5000 });
  assert('clean Bash produces no output', hookResult.trim() === '');
} catch (e) {
  assert('clean Bash hook did not crash', false, e.message);
}

// ─── Test 14: Hook processor — noisy Bash output (distill) ───
console.log('\n=== Test 14: Hook processor — noisy Bash output ===');
try {
  const noisyOutput = [];
  for (let i = 0; i < 45; i++) noisyOutput.push('  reify Node: timing reify:' + i);
  noisyOutput.push('  error: something broke');
  for (let i = 0; i < 10; i++) noisyOutput.push('  added ' + i + ' packages');
  const hookInput = JSON.stringify({ tool_name: 'Bash', command: 'npm install', output: noisyOutput.join('\n') });
  const hookResult = execSync(`node "${HOOK_JS}"`, { input: hookInput, encoding: 'utf8', timeout: 5000 });
  const response = JSON.parse(hookResult);
  assert('noisy Bash returns hookSpecificOutput', !!response.hookSpecificOutput);
  assert('hookSpecificOutput has PostToolUse', response.hookSpecificOutput.hookEventName === 'PostToolUse');
  assert('updatedToolOutput exists', typeof response.hookSpecificOutput.updatedToolOutput === 'string');
  assert('banner in output', response.hookSpecificOutput.updatedToolOutput.includes('output-distiller'));
  assert('error preserved in hook output', response.hookSpecificOutput.updatedToolOutput.includes('error: something broke'));
} catch (e) {
  assert('noisy Bash hook failed', false, e.message);
}

// ─── Test 15: Hook processor — invalid JSON (pass-through) ───
console.log('\n=== Test 15: Hook processor — invalid JSON ===');
try {
  const hookResult = execSync(`node "${HOOK_JS}"`, { input: 'not valid json', encoding: 'utf8', timeout: 5000 });
  assert('invalid JSON produces no output', hookResult.trim() === '');
} catch (e) {
  assert('invalid JSON hook did not crash', false, e.message);
}

// ─── Test 16: CLI — --file flag ───
console.log('\n=== Test 16: CLI — --file flag ===');
const tmpFile = path.join(__dirname, '_test_output.txt');
const testOutput = [];
for (let i = 0; i < 45; i++) testOutput.push('  reify Node: timing reify:' + i);
testOutput.push('  error: test error');
for (let i = 0; i < 10; i++) testOutput.push('  added ' + i + ' packages');
fs.writeFileSync(tmpFile, testOutput.join('\n'));
try {
  const cliResult = execSync(`node "${INDEX_JS}" --file "${tmpFile}"`, { encoding: 'utf8', timeout: 5000 });
  assert('CLI --file produces output', cliResult.length > 0);
  assert('CLI --file contains error', cliResult.includes('error: test error'));
  assert('CLI --file has reduction banner', cliResult.includes('→'));
} catch (e) {
  assert('CLI --file failed', false, e.message);
} finally {
  fs.unlinkSync(tmpFile);
}

// ─── Test 17: CLI — stdin pipe via temp file ───
console.log('\n=== Test 17: CLI — stdin pipe ===');
try {
  const pipeFile = path.join(__dirname, '_test_pipe.txt');
  const pipeInput = [];
  for (let i = 0; i < 45; i++) pipeInput.push('  reify Node: timing reify:' + i);
  pipeInput.push('  error: pipe test error');
  for (let i = 0; i < 10; i++) pipeInput.push('  added ' + i + ' packages');
  fs.writeFileSync(pipeFile, pipeInput.join('\n'));
  try {
    const cliResult = execSync(`node "${INDEX_JS}" --file "${pipeFile}"`, { encoding: 'utf8', timeout: 5000 });
    assert('CLI stdin pipe produces output', cliResult.length > 0);
    assert('CLI stdin contains error', cliResult.includes('error: pipe test error'));
  } finally {
    fs.unlinkSync(pipeFile);
  }
} catch (e) {
  assert('CLI stdin pipe failed', false, e.message);
}

// ─── Summary ───
console.log('\n' + '═'.repeat(50));
console.log(`\n  Total: ${total} | Passed: ${passed} | Failed: ${failed}`);
console.log('\n' + '═'.repeat(50));

if (failed > 0) {
  console.log('\n  ❌ Some tests failed!\n');
  process.exit(1);
} else {
  console.log('\n  ✅ All tests passed!\n');
  process.exit(0);
}
