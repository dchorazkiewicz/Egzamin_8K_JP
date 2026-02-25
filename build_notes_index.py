#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
from pathlib import Path


SUBJECT_DISPLAY = {
    "jezyk-polski": "Język polski",
    "matematyka": "Matematyka",
    "jezyk-angielski": "Język angielski",
}

HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")


def _year_sort_key(year: str) -> tuple[int, str]:
    if year.isdigit():
        return (-int(year), year)
    return (10**9, year)


def _prettify_name(stem: str) -> str:
    s = stem.replace("-", " ").replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s or stem


def _title_for_md(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as f:
            for _ in range(80):
                line = f.readline()
                if not line:
                    break
                m = HEADING_RE.match(line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return _prettify_name(path.stem)


def collect_notes(notes_root: Path) -> dict[str, dict[str, list[Path]]]:
    grouped: dict[str, dict[str, list[Path]]] = {}
    for path in sorted(notes_root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(notes_root)
        if len(rel.parts) < 3:
            # oczekujemy: <subject>/<year>/<file>.md
            continue
        subject, year = rel.parts[0], rel.parts[1]
        grouped.setdefault(subject, {}).setdefault(year, []).append(path)
    return grouped


def render_subject_markdown(
    subject: str,
    years: dict[str, list[Path]],
    *,
    docs_root: Path,
) -> str:
    lines: list[str] = []
    lines.append(f"# Notatki — {SUBJECT_DISPLAY.get(subject, subject)}\n")
    lines.append("Struktura: `docs/notes/<przedmiot>/<rok>/...` (osobno od `docs/pdf/`).")
    lines.append("")

    for year in sorted(years.keys(), key=_year_sort_key):
        lines.append(f'???+ info "{year}"')
        for md_path in sorted(years[year]):
            rel_from_docs = md_path.relative_to(docs_root).as_posix()
            title = _title_for_md(md_path)
            lines.append(f"    - [{title}]({rel_from_docs})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generuje stronę MkDocs z linkami do notatek/rozwiązań.")
    ap.add_argument("--notes-root", default="docs/notes", help="Katalog z notatkami (domyślnie: docs/notes)")
    ap.add_argument(
        "--out-dir",
        default="docs",
        help="Katalog wyjściowy na strony indeksów (domyślnie: docs)",
    )
    args = ap.parse_args()

    notes_root = Path(args.notes_root)
    out_dir = Path(args.out_dir)
    docs_root = out_dir

    if not notes_root.exists():
        raise SystemExit(f"Nie znaleziono katalogu notatek: {notes_root}")

    grouped = collect_notes(notes_root)

    subjects = list(SUBJECT_DISPLAY.keys())
    subjects += [s for s in sorted(grouped.keys()) if s not in SUBJECT_DISPLAY]

    written = 0
    for subject in subjects:
        if subject not in grouped:
            continue
        md = render_subject_markdown(subject, grouped[subject], docs_root=docs_root)
        out_path = out_dir / f"notatki-{subject}.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"Wygenerowano: {out_path}")
        written += 1

    if written == 0:
        raise SystemExit("Brak notatek do zindeksowania.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
