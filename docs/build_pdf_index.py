#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path


SUBJECT_DISPLAY = {
    "jezyk-polski": "Język polski",
    "matematyka": "Matematyka",
    "jezyk-angielski": "Język angielski",
}


def _year_sort_key(year: str) -> tuple[int, str]:
    if year.isdigit():
        return (-int(year), year)
    return (10**9, year)


def _pretty_title(subject: str, year: str, filename: str) -> str:
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    for prefix in (f"{subject}-{year}-", f"{subject}-{year}", f"{subject}-", f"{year}-", year):
        if stem.startswith(prefix):
            stem = stem.removeprefix(prefix)
            stem = stem.lstrip("-")
    stem = stem.replace("-", " ").strip()
    return stem or filename


def collect_pdfs(pdf_root: Path) -> dict[str, dict[str, list[Path]]]:
    grouped: dict[str, dict[str, list[Path]]] = {}
    for path in sorted(pdf_root.rglob("*.pdf")):
        rel = path.relative_to(pdf_root)
        if len(rel.parts) < 3:
            # oczekujemy: <subject>/<year>/<file>.pdf
            continue
        subject, year = rel.parts[0], rel.parts[1]
        grouped.setdefault(subject, {}).setdefault(year, []).append(path)
    return grouped


def render_markdown(grouped: dict[str, dict[str, list[Path]]], pdf_root: Path) -> str:
    lines: list[str] = []
    lines.append("# Arkusze PDF\n")
    lines.append(
        "Linki prowadzą do plików PDF trzymanych w repozytorium (kopiowanych do `site/` przy buildzie MkDocs)."
    )
    lines.append("")

    subjects = list(SUBJECT_DISPLAY.keys())
    subjects += [s for s in sorted(grouped.keys()) if s not in SUBJECT_DISPLAY]

    for subject in subjects:
        if subject not in grouped:
            continue
        lines.append(f"## {SUBJECT_DISPLAY.get(subject, subject)}")
        lines.append("")

        years = sorted(grouped[subject].keys(), key=_year_sort_key)
        for year in years:
            lines.append(f'???+ info "{year}"')
            for pdf_path in sorted(grouped[subject][year]):
                rel = pdf_path.relative_to(pdf_root).as_posix()
                title = _pretty_title(subject, year, pdf_path.name)
                # strona /pdfs/ -> ../pdf/<subject>/<year>/<file>.pdf
                lines.append(f"    - [{title}](../pdf/{rel})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generuje stronę MkDocs z linkami do PDF-ów.")
    ap.add_argument("--pdf-root", default="docs/pdf", help="Katalog z PDF-ami (domyślnie: docs/pdf)")
    ap.add_argument("--out", default="docs/pdfs.md", help="Docelowy plik markdown (domyślnie: docs/pdfs.md)")
    args = ap.parse_args()

    pdf_root = Path(args.pdf_root)
    out_path = Path(args.out)

    if not pdf_root.exists():
        raise SystemExit(f"Nie znaleziono katalogu PDF: {pdf_root}")

    grouped = collect_pdfs(pdf_root)
    md = render_markdown(grouped, pdf_root=pdf_root)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wygenerowano: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

