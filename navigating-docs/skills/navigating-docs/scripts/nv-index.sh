#!/usr/bin/env bash
# nv-index — generate INDEX.md (peta dokumen) untuk sebuah folder project.
# Pakai: nv-index <folder>   → menulis <folder>/INDEX.md
# Peta ini yang dibaca agent DULU (~1k token) sebelum membuka file spesifik.
set -uo pipefail

FOLDER="${1:?usage: nv-index <folder>}"
[ -d "$FOLDER" ] || { echo "folder tidak ada: $FOLDER"; exit 1; }
OUT="$FOLDER/INDEX.md"

title_of() { # ambil judul: H1 pertama .md, atau nama file
  local f="$1"
  case "$f" in
    *.md|*.markdown) grep -m1 -E '^#[[:space:]]+' "$f" 2>/dev/null | sed 's/^#[[:space:]]*//' ;;
    *) echo "$(basename "$f")" ;;
  esac
}

{
  echo "# INDEX — $(basename "$FOLDER")"
  echo
  echo "> Peta dokumen. Baca file ini dulu, lalu buka hanya file yang relevan."
  echo "> Regenerate: \`nv-index \"$(basename "$FOLDER")\"\`"
  echo
  echo "Total file: $(find "$FOLDER" -type f ! -name 'INDEX.md' | wc -l | tr -d ' ')"
  echo
  echo "## Struktur folder"
  echo '```'
  find "$FOLDER" -type d ! -path '*/.*' | sed "s|^$FOLDER|.|" | sort
  echo '```'
  echo
  echo "## Dokumen (markdown & teks)"
  find "$FOLDER" -type f \( -iname '*.md' -o -iname '*.txt' \) ! -name 'INDEX.md' ! -path '*/.*' | sort | while read -r f; do
    printf -- '- `%s` — %s\n' "${f#$FOLDER/}" "$(title_of "$f" | cut -c1-100)"
  done
  echo
  echo "## PDF / dokumen biner"
  find "$FOLDER" -type f \( -iname '*.pdf' -o -iname '*.docx' -o -iname '*.xlsx' \) ! -path '*/.*' | sort | while read -r f; do
    printf -- '- `%s` (%s KB)\n' "${f#$FOLDER/}" "$(( $(stat -c%s "$f") / 1024 ))"
  done
} > "$OUT"

echo "INDEX ditulis: $OUT ($(wc -l < "$OUT" | tr -d ' ') baris, $(du -k "$OUT" | cut -f1) KB)"