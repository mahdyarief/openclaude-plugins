#!/usr/bin/env bash
# office-mcp — idempotent environment setup
#
# This script is run at the start of every worker session to:
#   1. Force UTF-8 end-to-end (PYTHONUTF8=1, PYTHONIOENCODING=utf-8).
#   2. Add LibreOffice's `program/` directory to PATH (idempotently).
#   3. Activate the project virtualenv at .venv/ (create if missing).
#   4. Verify all required Python packages are importable.
#   5. Verify `soffice` is reachable (warn if not; export tools will skip).
#
# The script is idempotent: running it twice produces the same final state
# (the venv is reused, env vars are set to the same values, PATH is
# de-duplicated, etc.). It never deletes or recreates the venv.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ---------------------------------------------------------------------------
# 1. Encoding (UTF-8 end-to-end)
# ---------------------------------------------------------------------------
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# ---------------------------------------------------------------------------
# 2. Add LibreOffice to PATH (idempotent — skip if already present)
# ---------------------------------------------------------------------------
LO_PATHS=(
  "/c/Program Files/LibreOffice/program"
  "/c/Program Files (x86)/LibreOffice/program"
  "/Applications/LibreOffice.app/Contents/MacOS"
  "/usr/lib/libreoffice/program"
  "/usr/bin"
)
for p in "${LO_PATHS[@]}"; do
  case ":$PATH:" in
    *":$p:"*) ;;                 # already on PATH — skip
    *) export PATH="$p:$PATH" ;;  # prepend
  esac
done

# ---------------------------------------------------------------------------
# 3. Activate the venv (reuse the existing one)
# ---------------------------------------------------------------------------
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -d ".venv" ]; then
    if [ -f ".venv/Scripts/activate" ]; then
      # shellcheck disable=SC1091
      . .venv/Scripts/activate
    elif [ -f ".venv/bin/activate" ]; then
      # shellcheck disable=SC1091
      . .venv/bin/activate
    fi
  else
    echo "[init.sh] WARNING: .venv missing; creating one with system python"
    if command -v python >/dev/null 2>&1; then
      python -m venv .venv
    elif command -v python3 >/dev/null 2>&1; then
      python3 -m venv .venv
    else
      echo "[init.sh] ERROR: no python interpreter on PATH" >&2
      exit 1
    fi
    if [ -f ".venv/Scripts/activate" ]; then
      # shellcheck disable=SC1091
      . .venv/Scripts/activate
    elif [ -f ".venv/bin/activate" ]; then
      # shellcheck disable=SC1091
      . .venv/bin/activate
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 4. Verify dependencies
# ---------------------------------------------------------------------------
PY=".venv/Scripts/python.exe"
[ -f "$PY" ] || PY="python"
"$PY" -c "import mcp, docx, openpyxl, pptx, mammoth, defusedxml, pydantic, pytest, pypdf; print('[init.sh] ok: mcp, docx, openpyxl, pptx, mammoth, defusedxml, pydantic, pytest, pypdf')"

# ---------------------------------------------------------------------------
# 5. Verify soffice
# ---------------------------------------------------------------------------
if command -v soffice >/dev/null 2>&1; then
  echo "[init.sh] soffice: $(soffice --version 2>&1 | head -1)"
else
  echo "[init.sh] WARNING: soffice not on PATH; export_pdf/export_html tests will skip"
fi

echo "[init.sh] ready"
