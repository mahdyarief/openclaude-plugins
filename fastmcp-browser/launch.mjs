#!/usr/bin/env node
// Plugin entry point for fastmcp-browser.
//
// server/dist is not committed (upstream .gitignore), so a fresh marketplace
// install has no built server. On first run, or when the plugin version
// changes, this installs server dependencies and builds, then starts the MCP
// server. Build logs go to stderr only: stdout is the MCP stdio channel.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const server = join(root, 'server');
const entry = join(server, 'dist', 'src', 'index.js');
const stamp = join(server, 'dist', '.plugin-version');
const version = JSON.parse(readFileSync(join(root, '.claude-plugin', 'plugin.json'), 'utf8')).version;
const built = existsSync(stamp) ? readFileSync(stamp, 'utf8').trim() : null;

function npm(args) {
  // One command string (args are fixed literals): npm is npm.cmd on Windows and
  // needs a shell, and passing an args array with shell:true is deprecated.
  const result = spawnSync(`npm ${args.join(' ')}`, { cwd: server, stdio: ['ignore', 2, 2], shell: true });
  if (result.status !== 0) {
    console.error(`[fastmcp-browser] "npm ${args.join(' ')}" failed (exit ${result.status}).`);
    process.exit(1);
  }
}

if (!existsSync(entry) || built !== version) {
  console.error(`[fastmcp-browser] building server ${version} (first run or plugin update)...`);
  const install = existsSync(join(server, 'package-lock.json')) ? 'ci' : 'install';
  npm([install, '--ignore-scripts', '--no-audit', '--no-fund']);
  npm(['run', 'build']);
  writeFileSync(stamp, version);
}

await import(pathToFileURL(entry).href);
