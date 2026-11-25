#!/usr/bin/env node
// Sync fastmcp-browser/ with the upstream release of rayss868/fastmcp-browser.
//
// Usage:
//   node scripts/sync-fastmcp-browser.mjs            # latest upstream release
//   node scripts/sync-fastmcp-browser.mjs --tag v0.9.0
//
// Plugin-owned files (.claude-plugin/, .mcp.json, launch.mjs) and local build
// output (server/dist, server/node_modules) are kept; everything else in
// fastmcp-browser/ is replaced by the upstream tree. plugin.json "version" is
// set to the upstream version. Prints `changed=true|false` and `version=<x>`
// as the last lines (read by the GitHub workflow).
import { cpSync, existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const UPSTREAM = 'rayss868/fastmcp-browser';
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const target = join(repoRoot, 'fastmcp-browser');
const KEEP_TOP = new Set(['.claude-plugin', '.mcp.json', 'launch.mjs']);
const KEEP_SERVER = new Set(['dist', 'node_modules']);

const headers = { 'User-Agent': 'plugin-sync', Accept: 'application/vnd.github+json' };
if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;

async function latestTag() {
  const res = await fetch(`https://api.github.com/repos/${UPSTREAM}/releases/latest`, { headers });
  if (!res.ok) throw new Error(`GitHub API ${res.status} for latest release`);
  return (await res.json()).tag_name;
}

const tagArg = process.argv.indexOf('--tag');
const tag = tagArg > -1 ? process.argv[tagArg + 1] : await latestTag();
const version = tag.replace(/^v/, '');
const pluginJsonPath = join(target, '.claude-plugin', 'plugin.json');
const pluginJson = JSON.parse(readFileSync(pluginJsonPath, 'utf8'));

if (pluginJson.version === version && !process.argv.includes('--force')) {
  console.log(`already at upstream ${tag}`);
  console.log('changed=false');
  console.log(`version=${version}`);
  process.exit(0);
}

const work = mkdtempSync(join(tmpdir(), 'fastmcp-sync-'));
try {
  const tarball = join(work, 'src.tar.gz');
  const res = await fetch(`https://codeload.github.com/${UPSTREAM}/tar.gz/refs/tags/${tag}`, { headers: { 'User-Agent': 'plugin-sync' } });
  if (!res.ok) throw new Error(`download ${tag} failed: ${res.status}`);
  writeFileSync(tarball, Buffer.from(await res.arrayBuffer()));
  // Relative paths + cwd: GNU tar would read "C:\..." as a remote host.
  execFileSync('tar', ['-xzf', 'src.tar.gz'], { cwd: work });
  const extracted = readdirSync(work).find((n) => n.startsWith('fastmcp-browser-'));
  if (!extracted) throw new Error('unexpected tarball layout');
  const src = join(work, extracted);
  for (const keep of KEEP_TOP) {
    if (existsSync(join(src, keep))) throw new Error(`upstream now ships ${keep}; resolve by hand`);
  }

  for (const name of readdirSync(target)) {
    if (KEEP_TOP.has(name)) continue;
    if (name === 'server') {
      for (const sub of readdirSync(join(target, 'server'))) {
        if (!KEEP_SERVER.has(sub)) rmSync(join(target, 'server', sub), { recursive: true, force: true });
      }
      continue;
    }
    rmSync(join(target, name), { recursive: true, force: true });
  }
  cpSync(src, target, { recursive: true, force: true });

  pluginJson.version = version;
  writeFileSync(pluginJsonPath, JSON.stringify(pluginJson, null, 2) + '\n');
  console.log(`synced fastmcp-browser to upstream ${tag}`);
  console.log('changed=true');
  console.log(`version=${version}`);
} finally {
  rmSync(work, { recursive: true, force: true });
}
