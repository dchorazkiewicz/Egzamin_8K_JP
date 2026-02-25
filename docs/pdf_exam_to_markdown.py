#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF → Markdown converter for Polish exam sheets.

Primary backend: PyMuPDF (fitz) to preserve spans (bold/italic) and better layout.
Fallback backend: pdftotext -layout (when fitz isn't available).

Design goals:
- Keep logical structure: tasks as "### Zadanie N. (0–1)".
- Prefer readability for LLMs: remove visual noise, join hard line breaks into paragraphs,
  keep options and tables in Markdown-friendly form.
- Detect typical patterns: P/F tables and inline gaps with A/B/C/D in the middle of a sentence.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional


Backend = Literal["fitz", "pdftotext"]


# -----------------------------
# Regexes and noise filtering
# -----------------------------

TASK_RE = re.compile(r"^\s*Zadanie\s+(\d+)\.\s*\(([^)]+)\)\s*$")

PF_ONLY_RE = re.compile(r"^\s*P\s+F\s*$")
PF_ANY_RE = re.compile(r"\bP\b\s+\bF\b")
PF_TRAIL_RE = re.compile(r"^(.*?)(?:\s+P\s+F)\s*$")

# Visual answer blanks / placeholders
ANSWER_LINE_DOTS_RE = re.compile(r"^(?:\s*(?:[.\u2026]|\.)(?:\s*(?:[.\u2026]|\.))*)\s*$")
ANSWER_LINE_UNDERSCORE_RE = re.compile(r"^(?:\s*_+\s*){3,}$")
PLACEHOLDER_RUN_RE = re.compile(r"(?:[._\u2026·•‧∙⋅]{8,}|_{8,})")

# Inline gaps and options
OPTION_PAIR_SAME_LINE_RE = re.compile(r"^(?P<a>[A-D])\.\s+(?P<at>.+?)\s+(?P<b>[A-D])\.\s+(?P<bt>.+)$")
INLINE_OPTIONS_RE = re.compile(r"\b(?:[A-D](?:\s+[A-D]){1,3})\b")


REMOVE_LINE_RES = [
    re.compile(r"Więcej arkuszy znajdziesz na stronie:", re.IGNORECASE),
    re.compile(r"^\s*arkusze\.pl\s*$", re.IGNORECASE),
    re.compile(r"\bStrona\s+\d+\s+z\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{3,}-\d{3}-\d{4}\b"),  # np. OPOP-100-2602
    re.compile(r"^\s*PRZENIEŚ\b.*$", re.IGNORECASE),
    re.compile(r"Miejsce\s+dla", re.IGNORECASE),
    re.compile(r"Tabela\s+przeznaczona\s+dla\s+egzaminatora", re.IGNORECASE),
    re.compile(r"^\s*Brudnopis\b", re.IGNORECASE),
    re.compile(r"^\s*JĘZYK\s+POLSKI\s*$", re.IGNORECASE),
    re.compile(r"^\s*Egzamin\s+ósmoklasisty\s*$", re.IGNORECASE),
    re.compile(r"Zakres\s+środków", re.IGNORECASE),
]

NOISE_FRAGMENT_RES = [
    re.compile(r"\bPRZENIEŚ\b", re.IGNORECASE),
    re.compile(r"\bRZENIEŚ\b", re.IGNORECASE),
    re.compile(r"\bStrona\s+\d+\s+z\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{3,}\s*-\s*\d{3}\s*-\s*\d{4}\b"),
    re.compile(r"Więcej arkuszy znajdziesz na stronie:", re.IGNORECASE),
    re.compile(r"\barkusze\.pl\b", re.IGNORECASE),
]


def is_noise_line(line: str) -> bool:
    return any(rx.search(line) for rx in REMOVE_LINE_RES)


def is_noise_fragment(text: str) -> bool:
    """
    Detect fragments that are almost certainly headers/footers even when embedded in a line.
    Used mainly by the PyMuPDF backend.
    """
    t = text.strip()
    if not t:
        return False
    return any(rx.search(t) for rx in NOISE_FRAGMENT_RES)


INLINE_NOISE_STRIP_RES = [
    re.compile(r"PRZENIEŚ.*?KART[ĘE]\s+ODPOWIEDZI\s*!?", re.IGNORECASE),
    re.compile(r"\bNA\s+KART[ĘE]\s+ODPOWIEDZI\s*!?", re.IGNORECASE),
    re.compile(r"\bP\s*\d+\.\s*(?:I\s*\d+\.\s*)?NA\s+KART[ĘE]\s+ODPOWIEDZI\s*!?", re.IGNORECASE),
    re.compile(r"\bP\s*\d+\."),
    re.compile(r"\b[A-Z]{3,}\s*-\s*\d{3}\s*-\s*\d{4}\b"),
    re.compile(r"\bStrona\s+\d+\s+z\s+\d+\b", re.IGNORECASE),
    re.compile(r"Więcej arkuszy znajdziesz na stronie:.*$", re.IGNORECASE),
]


def strip_inline_noise_plain(text: str) -> str:
    out = text
    for rx in INLINE_NOISE_STRIP_RES:
        out = rx.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


# -----------------------------
# Data model
# -----------------------------


@dataclass(frozen=True)
class Task:
    number: int
    points: str
    lines: list[str]


# -----------------------------
# Text utilities
# -----------------------------


def dehyphenate(lines: list[str]) -> list[str]:
    """Join hyphenated words split at line end."""
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
            out.append(line[:-1] + lines[i + 1].lstrip())
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def normalize_whitespace(lines: list[str]) -> list[str]:
    """
    Normalize internal whitespace while preserving indentation for options.
    Also replaces long placeholder runs inside a line with [ODP].
    """
    out: list[str] = []
    for line in lines:
        prefix = re.match(r"^\s*", line).group(0)
        rest = line[len(prefix) :]
        rest = re.sub(r"\s{2,}", " ", rest).strip()
        if PLACEHOLDER_RUN_RE.search(rest):
            rest = PLACEHOLDER_RUN_RE.sub("[ODP]", rest)
            rest = re.sub(r"\s+\[ODP\]\s+", " [ODP] ", rest).strip()
        out.append((prefix + rest).rstrip())

    # compress blank lines (max 2)
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


def clean_lines(lines: list[str]) -> list[str]:
    """Remove obvious headers/footers and full-line answer placeholders."""
    out: list[str] = []
    for line in lines:
        if not line.strip():
            out.append("")
            continue
        if ANSWER_LINE_UNDERSCORE_RE.match(line):
            continue
        if ANSWER_LINE_DOTS_RE.match(line) and len(line.strip()) >= 3:
            continue
        if is_noise_line(line):
            continue
        out.append(line.rstrip())
    return out


def _is_sentence_end(s: str) -> bool:
    return bool(re.search(r'[.!?…:]"?[\)\]]?$', s))


def _is_keep_line_break(s: str) -> bool:
    """
    Heuristics for lines which should NOT be joined into a paragraph.
    """
    if not s:
        return True
    if s.startswith(("-", "*")):
        return True
    if s.startswith("–"):  # dialogues in reading texts
        return True
    if re.match(r"^[A-D]\.\s+", s):
        return True
    if re.match(r"^\d+\.\s+", s):
        return True
    if s.isupper() and len(s) <= 60:
        return True
    return False


def reflow_paragraphs(lines: list[str]) -> list[str]:
    """
    Join hard line breaks into paragraphs (best-effort).
    """
    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        joined = " ".join(paragraph).strip()
        if joined and not is_noise_line(joined):
            out.append(joined)
        paragraph = []

    for raw in lines:
        s = raw.strip()
        if not s:
            flush()
            out.append("")
            continue
        if is_noise_line(s):
            continue

        if not paragraph:
            paragraph.append(s)
            continue

        prev = paragraph[-1]
        keep_prev = _is_keep_line_break(prev)
        keep_curr = _is_keep_line_break(s)
        # Special-case: dialogue lines often wrap without repeating "–".
        # If previous line starts with "–" and doesn't end a sentence, and the next line is a continuation,
        # join them.
        if keep_prev and prev.startswith("–") and not _is_sentence_end(prev) and not s.startswith("–"):
            paragraph[-1] = f"{prev} {s}"
            continue

        if keep_prev or keep_curr or _is_sentence_end(prev):
            flush()
            paragraph.append(s)
            continue

        paragraph[-1] = f"{prev} {s}"

    flush()

    # compress blank lines (max 2)
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


# -----------------------------
# Task parsing / formatting
# -----------------------------


def split_tasks(all_lines: list[str]) -> tuple[list[str], list[Task]]:
    preface: list[str] = []
    tasks: list[Task] = []

    current: Optional[Task] = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current is None:
            return
        tasks.append(Task(number=current.number, points=current.points, lines=buf))
        current = None
        buf = []

    def plain_for_match(s: str) -> str:
        # strip markdown we might emit in fitz backend
        s = re.sub(r"</?u>", "", s)
        s = s.replace("*", "")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    for line in all_lines:
        m = TASK_RE.match(plain_for_match(line))
        if m:
            flush()
            current = Task(number=int(m.group(1)), points=m.group(2), lines=[])
            buf = []
            continue
        if current is None:
            preface.append(line)
        else:
            buf.append(line)

    flush()
    return preface, tasks


def format_blockquote(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in reflow_paragraphs(lines):
        if not line.strip():
            out.append(">")
        else:
            out.append(f"> {line.strip()}")
    while out and out[-1] == ">":
        out.pop()
    return out


def extract_pf_table(task_lines: list[str]) -> tuple[list[str], list[str], list[str]] | None:
    """
    Heurystyka tabel P/F:
    - wykryj pierwsze 'P F'
    - weź blok od ostatniej pustej linii przed nim jako start tabeli
    - każdy wiersz kończący się na 'P F' (lub z osobną linią 'P F') to nowe stwierdzenie
    """
    first_pf_idx = None
    for i, line in enumerate(task_lines):
        if PF_ANY_RE.search(line.replace("*", "")):
            first_pf_idx = i
            break
    if first_pf_idx is None:
        return None

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

        if PF_ONLY_RE.match(line.replace("*", "")):
            continue

        m = PF_TRAIL_RE.match(line)
        if m and PF_ANY_RE.search(line.replace("*", "")):
            content = m.group(1).strip()
            if content:
                row_buf.append(content)
            continue

        row_buf.append(line)

    if row_buf:
        flush_row()

    if not statements:
        return None

    table: list[str] = [
        "| Stwierdzenie | P | F |",
        "| :--- | :---: | :---: |",
    ]
    for stmt in statements:
        table.append(f"| {stmt} | [ ] | [ ] |")

    return instruction, table, remaining


def fix_inline_options(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """
    Detect inline option letters (A B / C D) in the middle of a sentence.
    Replace them with [LUKA], return detected gaps like [['A','B'], ['C','D']].
    """
    blanks: list[list[str]] = []
    out: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            out.append("")
            continue

        m = OPTION_PAIR_SAME_LINE_RE.match(s)
        if m:
            out.append(f"{m.group('a')}. {m.group('at').strip()}")
            out.append(f"{m.group('b')}. {m.group('bt').strip()}")
            continue

        def repl(match: re.Match) -> str:
            token = match.group(0)
            letters = [t for t in token.split() if t in {"A", "B", "C", "D"}]
            if len(letters) >= 2:
                blanks.append(letters)
                return "[LUKA]"
            return token

        if re.match(r"^[A-D]\.\s+", s):
            out.append(s)
        else:
            replaced = INLINE_OPTIONS_RE.sub(repl, s)
            replaced = re.sub(r"\[LUKA\]\s+\.", "[LUKA].", replaced)
            replaced = re.sub(r"\s{2,}", " ", replaced).strip()
            out.append(replaced)

    return out, blanks


def extract_lektury_markdown(all_lines: list[str]) -> list[str] | None:
    start = None
    for i, line in enumerate(all_lines):
        if "Lista lektur obowiązkowych" in line.replace("*", ""):
            start = i
            break
    if start is None:
        return None

    collected: list[str] = []
    for line in all_lines[start:]:
        if "Przeczytaj tekst" in line.replace("*", ""):
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
        if line.lower().startswith("inne lektury obowiązkowe"):
            items.append("### Inne lektury obowiązkowe")
            current_group = line
            continue
        m = re.match(r"^\d+\)\s*(.+)$", line)
        if m:
            if current_group is None:
                items.append("### Lista")
                current_group = "Lista"
            items.append(f"1. {m.group(1).strip()}")
            continue

    return items or None


def format_markdown(
    *,
    pdf_path: Path,
    title: str | None,
    preface: list[str],
    tasks: list[Task],
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
        out.append(f"### Zadanie {task.number}. ({task.points})")
        out.append("")

        raw_lines = task.lines

        # P/F table
        table = extract_pf_table(raw_lines)
        if table:
            instr_lines, table_md, remaining = table
            instr = [x.strip() for x in reflow_paragraphs(instr_lines) if x.strip()]
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

        # Inline gaps + paragraph reflow
        fixed, blanks = fix_inline_options(raw_lines)
        buf = reflow_paragraphs(fixed)

        # Options formatting (A./B./C./D. as list)
        formatted: list[str] = []
        in_option_list = False
        for s in buf:
            if in_option_list and not s.strip():
                continue
            if re.match(r"^[A-D]\.\s+", s):
                if not in_option_list:
                    if formatted and formatted[-1] != "":
                        formatted.append("")
                    in_option_list = True
                formatted.append(f"- {s}")
            else:
                in_option_list = False
                formatted.append(s)

        out.extend(formatted)

        if blanks:
            out.append("")
            out.append("**Luki w treści:**")
            out.append("")
            for i, letters in enumerate(blanks, start=1):
                out.append(f"- Luka {i}: wybór `{', '.join(letters)}`")

        out.append("")

    return "\n".join(out).rstrip() + "\n"


# -----------------------------
# PDF extraction backends
# -----------------------------


def extract_pages_pdftotext(pdf_path: Path) -> list[list[str]]:
    txt = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        text=True,
        errors="ignore",
    )
    return [[ln.rstrip("\n") for ln in page.splitlines()] for page in txt.split("\f")]


def _span_is_bold(font_name: str, flags: int, text: str) -> bool:
    """
    PyMuPDF gives flags and font name; flags are not stable across versions, so we
    rely mostly on font name heuristics.
    """
    if re.fullmatch(r"\(?\s*\d+\s*[–-]\s*\d+\s*\)?", text.strip()):
        return False
    name = font_name.lower()
    if "bold" in name:
        return True
    # fallback guess: some builds use bit 16 for bold
    if flags & (1 << 4):
        return True
    return False


def _span_is_italic(font_name: str, flags: int) -> bool:
    name = font_name.lower()
    if "italic" in name or "oblique" in name:
        return True
    # fallback guess: some builds use bit 2 for italic
    if flags & (1 << 1):
        return True
    return False


def _span_is_underline(font_name: str, flags: int) -> bool:
    name = font_name.lower()
    if "underline" in name:
        return True
    # fallback guess: underline bit
    if flags & (1 << 2):
        return True
    return False


def _join_parts(parts: list[str]) -> str:
    """
    Join span fragments into a single line with smarter spacing.
    """
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if not out:
            out.append(part)
            continue
        prev = out[-1]
        # join without space for e.g. "S" + "ZATAN" => "SZATAN"
        if re.fullmatch(r"\*{0,3}[A-Z]\*{0,3}", prev) and re.match(r"^\*{0,3}[A-Z]", part):
            out[-1] = prev + part
            continue
        if prev.endswith((" ", "\u00a0")) or part.startswith((",", ".", ":", ";", "!", "?", ")", "]")):
            out[-1] = prev + part
        else:
            out[-1] = prev + " " + part
    return "".join(out).strip()


def extract_pages_fitz(pdf_path: Path) -> list[list[str]]:
    """
    Extract pages as list of lines using PyMuPDF spans.

    NOTE: This requires `PyMuPDF` (module name `fitz`) installed in the active venv.
    """
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as e:  # pragma: no cover
        raise SystemExit(
            "Brak zależności `PyMuPDF` (fitz). Zainstaluj w venv: `./venv/bin/pip install PyMuPDF`."
        ) from e

    doc = fitz.open(str(pdf_path))
    pages: list[list[str]] = []
    for page in doc:
        d = page.get_text("dict")
        page_lines: list[str] = []
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                parts: list[str] = []
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text or not text.strip():
                        continue
                    font = span.get("font", "") or ""
                    flags = int(span.get("flags", 0) or 0)

                    t = text.replace("\u00a0", " ")
                    t = re.sub(r"\s{2,}", " ", t)

                    if is_noise_fragment(t):
                        continue

                    bold = _span_is_bold(font, flags, t)
                    italic = _span_is_italic(font, flags)
                    underline = _span_is_underline(font, flags)

                    if underline:
                        t = f"<u>{t}</u>"
                    if bold and italic:
                        t = f"***{t}***"
                    elif bold:
                        t = f"**{t}**"
                    elif italic:
                        t = f"*{t}*"

                    parts.append(t.strip())

                joined = _join_parts(parts)
                # normalize codes like "OPOP- 100 -2602" -> "OPOP-100-2602"
                joined = re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", joined)
                # if a footer/header leaked into a line, strip it on plain text (may drop styling)
                joined_plain = re.sub(r"</?u>", "", joined).replace("*", "")
                cleaned_plain = strip_inline_noise_plain(joined_plain)
                if cleaned_plain != joined_plain:
                    joined = cleaned_plain
                if joined:
                    page_lines.append(joined)
            page_lines.append("")
        pages.append(page_lines)
    return pages


# -----------------------------
# Pipeline / CLI
# -----------------------------


def build_markdown(
    *,
    pdf_path: Path,
    title: str | None,
    backend: Backend,
    start_at: Literal["all", "przeczytaj", "zadanie"],
    include_lektury: bool,
) -> str:
    if backend == "fitz":
        pages = extract_pages_fitz(pdf_path)
    else:
        pages = extract_pages_pdftotext(pdf_path)

    all_lines_full: list[str] = []
    for page in pages:
        cleaned = clean_lines(page)
        cleaned = dehyphenate(cleaned)
        cleaned = normalize_whitespace(cleaned)
        all_lines_full.extend(cleaned)
        all_lines_full.append("")

    # start-at trimming
    all_lines = list(all_lines_full)
    if start_at != "all":
        start_idx = None
        if start_at == "przeczytaj":
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

    preface, tasks = split_tasks(all_lines)
    lektury_md = extract_lektury_markdown(all_lines_full) if include_lektury else None

    return format_markdown(
        pdf_path=pdf_path,
        title=title,
        preface=preface,
        tasks=tasks,
        lektury_md=lektury_md,
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Konwersja arkusza PDF do Markdown (struktura zadań).")
    ap.add_argument("--in", dest="pdf_in", required=True, help="Wejściowy PDF")
    ap.add_argument("--out", dest="md_out", required=True, help="Wyjściowy plik Markdown")
    ap.add_argument("--title", default=None, help="Tytuł H1 (domyślnie: nazwa pliku)")
    ap.add_argument(
        "--backend",
        choices=["fitz", "pdftotext"],
        default="fitz",
        help="Backend ekstrakcji tekstu (domyślnie: fitz / PyMuPDF).",
    )
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
    args = ap.parse_args(argv)

    pdf_path = Path(args.pdf_in)
    out_path = Path(args.md_out)

    md = build_markdown(
        pdf_path=pdf_path,
        title=args.title,
        backend=args.backend,
        start_at=args.start_at,
        include_lektury=args.include_lektury,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wygenerowano: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
