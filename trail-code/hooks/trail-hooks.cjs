#!/usr/bin/env node
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const PKGS = ['@trailhq/trail-code', '@nanonets/graft', '@trailhq/trail'];
const BINS = process.platform === 'win32' ? ['trail.cmd', 'graft.cmd'] : ['trail', 'graft'];

function remembered() {
  try {
    const home = process.env.TRAIL_HOME ? path.resolve(process.env.TRAIL_HOME) : path.join(os.homedir(), '.trail');
    const file = path.join(home, 'install.json');
    const st = fs.statSync(file);
    if (process.getuid && (st.uid !== process.getuid() || (st.mode & 0o022))) return null;
    const d = JSON.parse(fs.readFileSync(file, 'utf8')).claudeDist;
    return typeof d === 'string' && path.isAbsolute(d) ? d : null;
  } catch { return null; }
}

function fromPkg(base) {
  return PKGS.map((name) => {
    try {
      const pkg = require.resolve(name + '/package.json', { paths: [base] });
      return path.join(path.dirname(pkg), 'dist', 'claude');
    } catch { return null; }
  });
}

function onPath() {
  const out = [];
  for (const d of (process.env.PATH || '').split(path.delimiter)) {
    if (!d || !path.isAbsolute(d)) continue;
    for (const bin of BINS) {
      const p = path.join(d, bin);
      if (!fs.existsSync(p)) continue;
      out.push(...fromPkg(d));
    }
  }
  return out;
}

function globalRoot() {
  try {
    const root = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32', windowsHide: true }).stdout;
    return (root || '').trim() || null;
  } catch { return null; }
}

function versionOf(distClaude) {
  try {
    return JSON.parse(fs.readFileSync(path.join(distClaude, '..', '..', 'package.json'), 'utf8')).version || null;
  } catch { return null; }
}

function newer(a, b) {
  if (!a) return false;
  if (!b) return true;
  const p = (v) => String(v).split('-')[0].split('.').map((n) => Number(n) || 0);
  const pa = p(a), pb = p(b);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d !== 0) return d > 0;
  }
  return false;
}

function best(dirs, name) {
  let bestDir = null, bestVer = null;
  for (const d of dirs) {
    if (!d || !fs.existsSync(path.join(d, name))) continue;
    const v = versionOf(d);
    if (bestDir === null || newer(v, bestVer)) { bestDir = d; bestVer = v; }
  }
  return bestDir;
}

function entry(name) {
  const dir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const cheap = [remembered(), ...fromPkg(dir), ...fromPkg(path.join(path.dirname(process.execPath), '..', 'lib')), ...onPath()];
  let hit = best(cheap, name);
  if (!hit) {
    const gr = globalRoot();
    if (gr) hit = best(PKGS.map((p) => path.join(gr, ...p.split('/'), 'dist', 'claude')), name);
  }
  return hit ? path.join(hit, name) : null;
}

const target = entry('hooks.js');
const args = process.argv.slice(2);
if (!target) process.exit(0);
const r = spawnSync(process.execPath, [target, ...args], { stdio: 'inherit', windowsHide: true });
process.exit(r.status == null ? 0 : r.status);
