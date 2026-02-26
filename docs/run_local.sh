#!/usr/bin/env bash
set -euo pipefail

# Minimalny wrapper do odpalania konwersji w trakcie pracy (łatwe do edycji).
#
# Użycie:
#   ./docs/run_local.sh jezyk-polski/2026/arkusz.pdf
#   ./docs/run_local.sh jezyk-polski/2026/arkusz.pdf pdftotext
#   ./docs/run_local.sh jezyk-polski/2026/arkusz.pdf pdftotext 1
#
# Zmienne (opcjonalnie):
#   BACKEND=pdftotext|fitz   (domyślnie: pdftotext)
#   DO_LAYOUT=1              (domyślnie: 1; JSON wymaga PyMuPDF)

PDF_REL="${1:-jezyk-polski/2026/jezyk-polski-2026-styczen-egzamin-osmoklasisty-probny.pdf}"
BACKEND="${2:-${BACKEND:-pdftotext}}"
DO_LAYOUT="${3:-${DO_LAYOUT:-1}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="${PY:-}"
if [[ -z "${PY}" ]]; then
  if [[ -x "${SCRIPT_DIR}/../venv/bin/python" ]]; then
    PY="${SCRIPT_DIR}/../venv/bin/python"
  else
    PY="python"
  fi
fi

"${PY}" "${SCRIPT_DIR}/pdf_exam_to_markdown.py" "${PDF_REL}" --backend "${BACKEND}"

