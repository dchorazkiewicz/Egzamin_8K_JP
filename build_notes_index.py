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


def render_markdown(grouped: dict[str, dict[str, list[Path]]], docs_root: Path, notes_root: Path) -> str:
    lines: list[str] = []
    lines.append("# Notatki i rozwiązania\n")
    lines.append("Struktura: `docs/notes/<przedmiot>/<rok>/...` (nie miesza się z `docs/pdf/`).")
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
            for md_path in sorted(grouped[subject][year]):
                rel_from_docs = md_path.relative_to(docs_root).as_posix()
                title = _title_for_md(md_path)
                lines.append(f"    - [{title}]({rel_from_docs})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generuje stronę MkDocs z linkami do notatek/rozwiązań.")
    ap.add_argument("--notes-root", default="docs/notes", help="Katalog z notatkami (domyślnie: docs/notes)")
    ap.add_argument("--out", default="docs/notatki.md", help="Docelowy plik markdown (domyślnie: docs/notatki.md)")
    args = ap.parse_args()

    notes_root = Path(args.notes_root)
    out_path = Path(args.out)
    docs_root = out_path.parent

    if not notes_root.exists():
        raise SystemExit(f"Nie znaleziono katalogu notatek: {notes_root}")

    grouped = collect_notes(notes_root)
    md = render_markdown(grouped, docs_root=docs_root, notes_root=notes_root)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wygenerowano: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

