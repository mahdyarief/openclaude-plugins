#!/usr/bin/env bash
# version: 1.0.0
#
# Gate for the ARS announce. Reads the UserPromptSubmit event JSON on stdin
# and runs announce-ars-loaded.sh only when the submitted prompt is an
# ARS slash command (/ars or /ars-*). Every other prompt produces no output,
# so a session that never touches ARS stays quiet.
#
# The announce script is left untouched: this wrapper rewrites its
# SessionStart envelope to UserPromptSubmit and drops the user-facing
# systemMessage, then emits the result unchanged.
#
# Exit codes:
#   0    Always. A missing or failing announce degrades to no output.

set -euo pipefail

INPUT=""
if [[ ! -t 0 ]]; then
  INPUT=$(cat)
fi

# Pull the prompt text out of the hook payload. Same tolerant pattern the
# announce script uses for `source`: single-line or multi-line JSON, any
# whitespace around the colon, escaped characters left intact.
PROMPT=""
if [[ -n "${INPUT}" ]]; then
  if [[ "${INPUT}" =~ \"prompt\"[[:space:]]*:[[:space:]]*\"(([^\"\\]|\\.)*)\" ]]; then
    PROMPT="${BASH_REMATCH[1]}"
  fi
fi

# Trim leading whitespace, then require the /ars command prefix.
TRIMMED="${PROMPT#"${PROMPT%%[![:space:]]*}"}"
case "${TRIMMED}" in
  /ars|/ars\ *|/ars-*) ;;
  *) exit 0 ;;
esac

# Builtins only, so the gate survives a minimal PATH on plugin installs.
_SELF="${BASH_SOURCE[0]}"
_DIR="${_SELF%/*}"
if [[ "${_DIR}" == "${_SELF}" ]]; then _DIR="."; fi

# No network mid-prompt: the update reminder belongs to session start only.
OUT=$(printf '%s' "${INPUT}" | ARS_UPDATE_CHECK=0 bash "${_DIR}/announce-ars-loaded.sh" 2>/dev/null) || exit 0
if [[ -z "${OUT}" ]]; then
  exit 0
fi

# Rewrite the envelope for this event and drop systemMessage (the user
# already knows they typed /ars; the context injection is what matters).
# After the strip, OUT is the previous hookSpecificOutput value followed by
# the root object's closing brace. Re-wrap it under a fresh hookSpecificOutput
# so the harness reads additionalContext from this event.
OUT="${OUT/\"hookEventName\":\"SessionStart\"/\"hookEventName\":\"UserPromptSubmit\"}"
OUT="${OUT#*\"systemMessage\":*,\"hookSpecificOutput\":}"
case "${OUT}" in
  *"}}" ) OUT="${OUT%?}" ;;
esac
OUT="{\"hookSpecificOutput\":${OUT}}"

printf '%s\n' "${OUT}"
exit 0
