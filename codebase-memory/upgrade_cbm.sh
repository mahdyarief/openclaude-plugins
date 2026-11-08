#!/usr/bin/env bash
# Upgrade codebase-memory-mcp on aspire to v0.12.1 (linux-amd64).
# Verifies SHA-256 against upstream checksums.txt before swapping the binary.
set -euo pipefail

BIN=/home/dy/.local/bin/codebase-memory-mcp
CACHE=/home/dy/.cache/codebase-memory-mcp
TMP=$(mktemp -d /tmp/cbm-upgrade.XXXXXX)
VERSION=v0.12.1
BASE="https://github.com/DeusData/codebase-memory-mcp/releases/download/${VERSION}"
TARBALL="codebase-memory-mcp-linux-amd64.tar.gz"
EXPECTED="8453015145f072c1b9b019cbdd02cea8cc6f18cc5e116036dd20992631c638c7"

echo "=== old version ==="
"$BIN" --version 2>&1 | head -1 || true
echo "=== downloading ${TARBALL} + checksums.txt ==="
curl -fsSL -o "$TMP/$TARBALL" "$BASE/$TARBALL"
curl -fsSL -o "$TMP/checksums.txt" "$BASE/checksums.txt"

echo "=== verifying sha256 ==="
cd "$TMP"
ACTUAL=$(sha256sum "$TARBALL" | awk '{print $1}')
echo "expected=$EXPECTED"
echo "actual  =$ACTUAL"
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "MISMATCH - aborting"
  exit 1
fi
echo "checksum OK"

echo "=== extracting ==="
tar -xzf "$TARBALL"
NEW=$(find . -maxdepth 2 -type f -perm -u+x -name codebase-memory-mcp | head -1)
if [ -z "$NEW" ]; then
  echo "no executable found in tarball"
  tar -tzf "$TARBALL" | head -20
  exit 1
fi
echo "extracted: $NEW"

echo "=== stopping daemon + committed clients ==="
for p in $(pgrep -f "codebase-memory-mcp"); do
  echo "TERM pid=$p"
  kill -TERM "$p" 2>/dev/null || true
done
sleep 3
for p in $(pgrep -f "codebase-memory-mcp"); do
  echo "KILL pid=$p"
  kill -KILL "$p" 2>/dev/null || true
done

echo "=== installing new binary ==="
install -m 0755 -o dy -g dy "$NEW" "$BIN"
"$BIN" --version

echo "=== preserving safe defaults in config ==="
"$BIN" config set auto_watch false
"$BIN" config set auto_index_limit 1000
"$BIN" config list | grep -E "auto_watch|auto_index"

echo "=== cleanup ==="
rm -rf "$TMP"
echo "UPGRADE DONE"