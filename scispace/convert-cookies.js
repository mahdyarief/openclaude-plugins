#!/usr/bin/env node
// convert-cookies.js — Convert a Netscape-format cookies.txt (exported by the
// "Get cookies.txt LOCALLY" Chrome extension) into Playwright storage-state.json.
//
// Usage:
//   cp ~/Downloads/cookies.txt ./cookies.txt
//   node convert-cookies.js
//
// Writes storage-state.json next to this script (the file the plugin loads).

const fs = require("fs");
const path = require("path");

const INPUT = path.join(__dirname, "cookies.txt");
const OUTPUT = path.join(__dirname, "storage-state.json");

if (!fs.existsSync(INPUT)) {
  console.error(
    "cookies.txt not found next to this script. Export it first with the 'Get cookies.txt LOCALLY' extension on a signed-in scispace.com tab."
  );
  process.exit(1);
}

const lines = fs.readFileSync(INPUT, "utf8").split("\n");
const cookies = [];

for (const line of lines) {
  if (line.startsWith("#") || !line.trim()) continue;
  const [domain, , pathStr, secure, expires, name, value] = line.split("\t");
  if (!name) continue;
  cookies.push({
    name,
    value,
    domain: domain.startsWith(".") ? domain : "." + domain,
    path: pathStr || "/",
    expires: parseInt(expires, 10) || -1,
    httpOnly: true, // cookies.txt does not mark this; auth sessions are usually HttpOnly
    secure: secure === "TRUE",
    sameSite: "Lax",
  });
}

fs.writeFileSync(OUTPUT, JSON.stringify({ cookies, origins: [] }, null, 2));
console.log("Converted " + cookies.length + " cookies → storage-state.json");
