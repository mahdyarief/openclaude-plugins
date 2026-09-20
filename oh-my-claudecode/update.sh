#!/bin/bash
# Update oh-my-claudecode (OMC) plugin di OpenClaude.
# Usage: ./update.sh [version]   (default: versi terbaru dari npm)
set -euo pipefail

NAME=oh-my-claudecode
CACHE="$HOME/.openclaude/plugins/cache/local-plugins/$NAME"
INSTALLED="$HOME/.openclaude/plugins/installed_plugins.json"
MP_DIR="$HOME/.openclaude/plugins/marketplaces/local-plugins/$NAME"
MP_JSON="$HOME/.openclaude/plugins/marketplaces/local-plugins/.claude-plugin/marketplace.json"

VER="${1:-$(npm view oh-my-claude-sisyphus version)}"
DEST="$CACHE/$VER"

if [ -d "$DEST" ]; then
  echo "Versi $VER sudah ada di cache. Hapus manual dulu jika ingin re-clone."
  exit 1
fi

echo "==> Clone OMC v$VER ke cache"
mkdir -p "$CACHE"
git clone --depth 1 --branch "v$VER" "https://github.com/Yeachan-Heo/oh-my-claudecode" "$DEST" 2>/dev/null \
  || git clone --depth 1 "https://github.com/Yeachan-Heo/oh-my-claudecode" "$DEST"
SHA=$(git -C "$DEST" rev-parse HEAD)

echo "==> Update installed_plugins.json"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
TMP=$(mktemp)
jq --arg ver "$VER" --arg path "$DEST" --arg now "$NOW" --arg sha "$SHA" \
  '.["'"$NAME"'@local-plugins"] = [{
     "scope": "user",
     "installPath": $path,
     "version": $ver,
     "installedAt": $now,
     "lastUpdated": $now,
     "gitCommitSha": $sha
   }]' "$INSTALLED" > "$TMP" && mv "$TMP" "$INSTALLED"

echo "==> Sync marketplace folder"
mkdir -p "$MP_DIR/.claude-plugin"
cp "$DEST/.claude-plugin/plugin.json" "$MP_DIR/.claude-plugin/"
cp -r "$DEST/skills" "$DEST/commands" "$DEST/agents" "$DEST/hooks" "$MP_DIR/" 2>/dev/null || true
cp "$DEST/.mcp.json" "$MP_DIR/" 2>/dev/null || true

echo "==> Update marketplace.json description"
TMP2=$(mktemp)
jq --arg desc "oh-my-claudecode (OMC) v$VER — Teams-first multi-agent orchestration." \
  '(.[] | select(.name == "oh-my-claudecode") | .description) |= $desc' "$MP_JSON" > "$TMP2" \
  && mv "$TMP2" "$MP_JSON"

echo "==> Cleanup cache versi lama (opsional, biarkan jika ingin rollback)"
ls "$CACHE" | grep -v "^$VER$" || true

echo "Selesai. Buka OpenClaude lalu jalankan /reload-plugins."
