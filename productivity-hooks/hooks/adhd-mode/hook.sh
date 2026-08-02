#!/usr/bin/env bash
# ADHD Mode — PostToolUse hook wrapper (portable)
# Delegates to hook.js for JSON parsing and ADHD processing.
# Resolves its own location so it works from any plugin install path.

cat | node "$(dirname "$0")/hook.js"
