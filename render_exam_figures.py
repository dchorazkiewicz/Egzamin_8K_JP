#!/usr/bin/env python3
"""Renders only the six ORIGINAL photos of task 9 from the CKE exam PDF.

No text extraction, OCR or Markdown conversion. The page content is authored
separately as accessible HTML; this tiny renderer is only for exact visual art.
"""
from pathlib import Path
import fitz

PDF = Path("docs/pdf/jezyk-polski/2026/jezyk-polski-2026-egzamin-osmoklasisty.pdf")
OUT = Path("docs/assets/exam-images/polski-2026-zadanie-9.png")

if __name__ == "__main__":
    if not PDF.is_file():
        raise SystemExit(f"Missing source PDF: {PDF}")
    with fitz.open(PDF) as doc:
        if len(doc) < 10:
            raise SystemExit("Wrong source: fewer than 10 pages")
        page = doc[9]  # PDF page 10: six numbered photographs in task 9
        clip = fitz.Rect(72, 172, page.rect.width-66, 438)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip, alpha=False)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(OUT)
        print(f"Saved original six task-9 photographs: {OUT} ({pixmap.width}×{pixmap.height})")
