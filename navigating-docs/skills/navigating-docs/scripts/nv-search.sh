#!/usr/bin/env bash
# nv-search — cari teks di folder dokumen tanpa index berat.
# Pakai: nv-search <folder> <query...> [--max N] [--pdf]
# Query multi-kata dipecah jadi OR per kata (mirip keyword search ringan),
# kecuali dibungkus kutip ganda "..." → diperlakukan sebagai frasa literal.
# PDF: OPT-IN via --pdf (pdftotext semua PDF; lambat ~40s/68 file di Git Bash).
#      Tanpa --pdf: teks saja (<1s) — pdftotext 1-2 PDF spesifik dari INDEX.md lebih cepat.
# Output: path:line:isi  (hemat token, hanya baris match, max 300 char/baris)
set -uo pipefail

FOLDER="${1:?usage: nv-search <folder> <query...> [--max N] [--pdf]}"
shift
MAX=20
SCAN_PDF=0
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --max) MAX="${2:-20}"; shift 2 ;;
    --pdf) SCAN_PDF=1; shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
[ "${#ARGS[@]}" -gt 0 ] || { echo "usage: nv-search <folder> <query...> [--max N] [--pdf]"; exit 1; }

command -v rg >/dev/null 2>&1 || { echo "rg tidak ditemukan di PATH"; exit 1; }

# Bangun pola OR: "kata1|kata2|kata3" (case-insensitive via -i).
# Frasa yang dibungkus "..." dipertahankan sebagai satu alternatif literal.
PATTERN=""
for w in "${ARGS[@]}"; do
  [ -n "$PATTERN" ] && PATTERN="$PATTERN|"
  # escape regex chars kecuali spasi-dalam-frasa
  esc=$(printf '%s' "$w" | sed 's/[][(){}.^$*+?|\\]/\\&/g')
  PATTERN="$PATTERN$esc"
done

emit() { cut -c1-300; }

echo "## Text files (md/txt/yaml/json/csv/py/sql)"
rg -n --no-heading -i -m2 -g '!*.pdf' -g '!*.docx' -g '!*.xlsx' \
   -e "$PATTERN" "$FOLDER" 2>/dev/null | head -n "$MAX" | emit

echo
if [ "$SCAN_PDF" = "1" ]; then
echo "## PDF files (via pdftotext, file <=20MB, 4 paralel)"
if command -v pdftotext >/dev/null 2>&1; then
  search_one_pdf() {
    local f="$1" pat="$2"
    pdftotext -q "$f" - 2>/dev/null | grep -Ein -m2 -- "$pat" | \
      sed "s|^|${f}:|" | cut -c1-300
  }
  export -f search_one_pdf
  find "$FOLDER" -type f -iname '*.pdf' -size -20480k -print0 2>/dev/null |
    xargs -0 -n1 -P4 bash -c 'search_one_pdf "$2" "$1"' _ "$PATTERN" |
    head -n "$MAX"
  NSKIP=$(find "$FOLDER" -type f -iname '*.pdf' -size +20480k 2>/dev/null | wc -l | tr -d ' ')
  [ "$NSKIP" != "0" ] && echo "(skip $NSKIP PDF >20MB — pdftotext per file spesifik dari INDEX.md)"
else
  echo "(pdftotext tidak ada — skip PDF)"
fi
else
  NPdf=$(find "$FOLDER" -type f -iname '*.pdf' -size -20480k 2>/dev/null | wc -l | tr -d ' ')
  [ "$NPdf" != "0" ] && echo "(PDF tidak discan — tambah flag --pdf untuk $NPdf file, atau pdftotext file spesifik dari INDEX.md)"
fi

echo
echo "## DOCX files (via pandoc)"
if command -v pandoc >/dev/null 2>&1; then
  find "$FOLDER" -type f -iname '*.docx' -print0 2>/dev/null | while IFS= read -r -d '' f; do
    pandoc --from=docx --to=plain "$f" 2>/dev/null | grep -Ein -m2 -- "$PATTERN" | while IFS=: read -r ln txt; do
      printf '%s:%s:%s\n' "$f" "$ln" "$txt" | cut -c1-300
    done
  done | head -n "$MAX"
fi
