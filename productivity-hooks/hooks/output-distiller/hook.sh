#!/usr/bin/env bash
# Output Distiller — PostToolUse hook wrapper (portable)
# Delegates to hook.js for JSON parsing and distillation.
# Resolves its own location so it works from any plugin install path.

cat | node "$(dirname "$0")/hook.js"
