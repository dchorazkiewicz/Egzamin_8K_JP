#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


TASK_RE = re.compile(r"^\s*Zadanie\s+(\d+)\.\s*\(([^)]+)\)\s*$")
PF_ONLY_RE = re.compile(r"^\s*P\s+F\s*$")
PF_ANY_RE = re.compile(r"\bP\b\s+\bF\b")
PF_TRAIL_RE = re.compile(r"^(.*?)(?:\s+P\s+F)\s*$")
REMOVE_LINE_RES = [
    re.compile(r"Więcej arkuszy znajdziesz na stronie:", re.IGNORECASE),
    re.compile(r"^\s*arkusze\.pl\s*$", re.IGNORECASE),
    re.compile(r"\bStrona\s+\d+\s+z\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{3,}-\d{3}-\d{4}\b"),  # np. OPOP-100-2602
    re.compile(r"^\s*PRZENIEŚ\b.*$", re.IGNORECASE),
]


@dataclass(frozen=True)
class Task:
    number: int
    points: str
    lines: list[str]


def _run(*cmd: str) -> str:
    return subprocess.check_output(list(cmd), text=True, errors="ignore")


def extract_pages(pdf_path: Path) -> list[list[str]]:
    txt = _run("pdftotext", "-layout", str(pdf_path), "-")
    pages_raw = txt.split("\f")
    pages: list[list[str]] = []
    for p in pages_raw:
        lines = [ln.rstrip("\n") for ln in p.splitlines()]
        pages.append(lines)
    return pages


def clean_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append("")
            continue
        if any(rx.search(line) for rx in REMOVE_LINE_RES):
            continue
        out.append(line.rstrip())
    return out


def dehyphenate(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            line.endswith("-")
            and i + 1 < len(lines)
            and lines[i + 1]
            and lines[i + 1].lstrip()[:1].islower()
        ):
            joined = line[:-1] + lines[i + 1].lstrip()
            out.append(joined)
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def normalize_whitespace(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        # zachowujemy wcięcia dla opcji (A., B., …), ale redukujemy wielokrotne spacje w środku
        prefix = re.match(r"^\s*", line).group(0)
        rest = line[len(prefix) :]
        rest = re.sub(r"\s{2,}", " ", rest).strip()
        out.append((prefix + rest).rstrip())
    # kompresja nadmiaru pustych linii (max 2)
    compact: list[str] = []
    blanks = 0
    for line in out:
        if not line.strip():
            blanks += 1
            if blanks <= 2:
                compact.append("")
        else:
            blanks = 0
            compact.append(line)
    return compact


def split_tasks(all_lines: list[str]) -> tuple[list[str], list[Task]]:
    preface: list[str] = []
    tasks: list[Task] = []

    current_task: Task | None = None
    current_lines: list[str] = []

    def flush_task() -> None:
        nonlocal current_task, current_lines
        if current_task is None:
            return
        tasks.append(Task(number=current_task.number, points=current_task.points, lines=current_lines))
        current_task = None
        current_lines = []

    for line in all_lines:
        m = TASK_RE.match(line)
        if m:
            flush_task()
            current_task = Task(number=int(m.group(1)), points=m.group(2), lines=[])
            current_lines = []
            continue
        if current_task is None:
            preface.append(line)
        else:
            current_lines.append(line)

    flush_task()
    return preface, tasks


def format_blockquote(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append(">")
        else:
            out.append(f"> {line.strip()}")
    # usuń trailing puste quote-linie
    while out and out[-1] == ">":
        out.pop()
    return out


def extract_pf_table(task_lines: list[str]) -> tuple[list[str], list[str], list[str]] | None:
    """
    Heurystyka dla tabel P/F po pdftotext -layout:
    - stwierdzenie w 1–N liniach
    - wiersze oddzielone pustą linią
    - markery 'P F' mogą być osobno lub na końcu wiersza
    """
    first_pf_idx = None
    for i, line in enumerate(task_lines):
        if PF_ANY_RE.search(line):
            first_pf_idx = i
            break

    if first_pf_idx is None:
        return None

    # tabela zwykle zaczyna się po ostatniej pustej linii przed pierwszym 'P F'
    table_start = 0
    for j in range(first_pf_idx, -1, -1):
        if not task_lines[j].strip():
            table_start = j + 1
            break

    instruction = task_lines[:table_start]
    table_region = task_lines[table_start:]

    statements: list[str] = []
    row_buf: list[str] = []
    remaining: list[str] = []

    def flush_row() -> None:
        nonlocal row_buf
        stmt = " ".join(x.strip() for x in row_buf if x.strip())
        stmt = re.sub(r"\s+", " ", stmt).strip()
        if stmt:
            statements.append(stmt)
        row_buf = []

    in_table = True
    for line in table_region:
        if not in_table:
            remaining.append(line)
            continue

        s = line.strip()
        if not s:
            if row_buf:
                flush_row()
            continue

        if re.match(r"^\s*PRZENIEŚ\b", line, flags=re.IGNORECASE):
            if row_buf:
                flush_row()
            in_table = False
            continue

        if PF_ONLY_RE.match(line):
            # same markery kolumn – pomijamy
            continue

        m = PF_TRAIL_RE.match(line)
        if m and PF_ANY_RE.search(line):
            content = m.group(1).strip()
            if content:
                row_buf.append(content)
            continue

        row_buf.append(line)

    if row_buf:
        flush_row()

    if not statements:
        return None

    table: list[str] = []
    table.append("| Stwierdzenie | P | F |")
    table.append("| :--- | :---: | :---: |")
    for stmt in statements:
        table.append(f"| {stmt} | [ ] | [ ] |")

    return instruction, table, remaining


def looks_like_reading_block(lines: list[str]) -> bool:
    joined = " ".join(l.strip() for l in lines if l.strip())
    if not joined:
        return False
    if "Przeczytaj" in joined or "Przeczytaj tekst" in joined:
        return True
    if re.search(r"\[\s*\d+\s*wyrazy\s*\]", joined):
        return True
    return False


def extract_lektury_markdown(all_lines: list[str]) -> list[str] | None:
    start = None
    for i, line in enumerate(all_lines):
        if "Lista lektur obowiązkowych" in line:
            start = i
            break
    if start is None:
        return None

    collected: list[str] = []
    for line in all_lines[start:]:
        if "Przeczytaj tekst" in line:
            break
        collected.append(line.strip())

    items: list[str] = []
    current_group: str | None = None
    for line in collected:
        if not line:
            continue
        if line.startswith("Klasy "):
            current_group = line
            items.append(f"### {current_group}")
            continue
        m = re.match(r"^\d+\)\s*(.+)$", line)
        if m:
            if current_group is None:
                items.append("### Lista")
                current_group = "Lista"
            items.append(f"1. {m.group(1).strip()}")
            continue
        # krótkie nagłówki w obrębie listy (np. Inne lektury…)
        if line.endswith(":") or line.lower().startswith("inne lektury obowiązkowe"):
            items.append(f"### {line.rstrip(':').strip()}")
            current_group = line
            continue

    return items or None


def format_markdown(
    pdf_path: Path,
    title: str | None,
    preface: list[str],
    tasks: list[Task],
    *,
    lektury_md: list[str] | None,
) -> str:
    out: list[str] = []
    out.append(f"# {title or pdf_path.stem}")
    out.append("")
    out.append(f"Źródło PDF: `{pdf_path.as_posix()}`")
    out.append("")

    if lektury_md:
        out.append("## Lektury obowiązkowe")
        out.append("")
        out.extend(lektury_md)
        out.append("")

    preface_clean = [l for l in preface if l.strip()]
    if preface_clean:
        out.append("---")
        out.extend(format_blockquote(preface_clean))
        out.append("")

    for task in tasks:
        out.append(f"### Zadanie {task.number}. (${task.points}$)")
        out.append("")

        lines = [l for l in task.lines]

        # jeśli w środku pojawia się \"Przeczytaj tekst\" przed kolejnymi zadaniami, zostawiamy jako cytat
        # (prosta wersja: osobne akapity w blockquote)
        table = extract_pf_table(lines)
        if table:
            instr_lines, table_md, remaining = table
            instr = [x.strip() for x in instr_lines if x.strip()]
            if instr:
                out.append(re.sub(r"\s+", " ", " ".join(instr)).strip())
                out.append("")
            out.extend(table_md)
            out.append("")
            rem = [l.strip() for l in remaining if l.strip()]
            if rem:
                out.extend(rem)
                out.append("")
            continue

        # domyślnie: wypisz treść jako tekst + listy
        buf: list[str] = []
        for line in lines:
            s = line.strip()
            if not s:
                if buf and buf[-1] != "":
                    buf.append("")
                continue
            buf.append(s)

        # lekka obróbka list A./B./C./D.
        formatted: list[str] = []
        for s in buf:
            if re.match(r"^[A-D]\.\s+", s):
                if formatted and formatted[-1] != "":
                    formatted.append("")
                formatted.append(f"- {s}")
            else:
                formatted.append(s)

        out.extend(formatted)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Konwersja arkusza PDF do Markdown (struktura zadań).")
    ap.add_argument("--in", dest="pdf_in", required=True, help="Wejściowy PDF")
    ap.add_argument("--out", dest="md_out", required=True, help="Wyjściowy plik Markdown")
    ap.add_argument("--title", default=None, help="Tytuł H1 (domyślnie: nazwa pliku)")
    ap.add_argument(
        "--start-at",
        choices=["all", "przeczytaj", "zadanie"],
        default="przeczytaj",
        help="Od którego miejsca zacząć konwersję (domyślnie: pierwsze wystąpienie 'Przeczytaj').",
    )
    ap.add_argument(
        "--include-lektury",
        action="store_true",
        help="Jeśli wykryje listę lektur w arkuszu, doda ją jako osobną sekcję Markdown.",
    )
    args = ap.parse_args()

    pdf_path = Path(args.pdf_in)
    out_path = Path(args.md_out)

    pages = extract_pages(pdf_path)
    all_lines_full: list[str] = []
    for page in pages:
        cleaned = clean_lines(page)
        cleaned = dehyphenate(cleaned)
        cleaned = normalize_whitespace(cleaned)
        all_lines_full.extend(cleaned)
        all_lines_full.append("")  # separator stron

    if args.start_at != "all":
        start_idx = None
        if args.start_at == "przeczytaj":
            for i, line in enumerate(all_lines_full):
                if "Przeczytaj" in line:
                    start_idx = i
                    break
        if start_idx is None:
            for i, line in enumerate(all_lines_full):
                if TASK_RE.match(line):
                    start_idx = i
                    break
        if start_idx is not None:
            all_lines = all_lines_full[start_idx:]
        else:
            all_lines = list(all_lines_full)
    else:
        all_lines = list(all_lines_full)

    preface, tasks = split_tasks(all_lines)
    lektury_md = extract_lektury_markdown(all_lines_full) if args.include_lektury else None
    md = format_markdown(pdf_path, args.title, preface, tasks, lektury_md=lektury_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wygenerowano: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
