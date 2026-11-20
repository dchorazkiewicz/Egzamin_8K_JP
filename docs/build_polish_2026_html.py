#!/usr/bin/env python3
"""Build a real scrolling HTML edition of Polish E8 2026 from locally stored CKE PDFs.

Converts all original source passages, each question and its possible answers.
Preserves bold/italic typography; embeds a cropped image for photographic tasks.
Adds editorial explanations already reviewed in the site. Never uses OCR when the
PDF has a text layer and refuses to overwrite the guide if tasks go missing.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import fitz
from bs4 import BeautifulSoup

SOURCE = Path("docs/pdf/jezyk-polski/2026/jezyk-polski-2026-egzamin-osmoklasisty.pdf")
GUIDE = Path("docs/opracowania/polski-2026.md")
IMAGE_DIR = Path("docs/assets/opracowania/polski-2026")
TASKS = {
    1: 5, 2: 5, 3: 6, 4: 6, 5: 6, 6: 7, 7: 7, 8: 8,
    9: 9, 10: 10, 11: 12, 12: 12, 13: 12, 14: 13,
    15: 13, 16: 13, 17: 14, 18: 15,
}
NOISE = re.compile(
    r"(Więcej arkuszy znajdziesz|arkusze\.pl|PRZENIEŚ ROZWIĄZANI|"
    r"PRZENIEŚ ROZWIĄZANIE|Strona \d+ z \d+|OPOP-100-2605|"
    r"^Miejsce dla egzaminatora|^.{0,5}[_…\.]{7,}|^\s*\d{1,2}\s*$)",
    re.I
)
BOILERPLATE = re.compile(r"^[\s\._…\-–]+$")


def task_marker(page: fitz.Page, number: int) -> float:
    found = page.search_for(f"Zadanie {number}.")
    if not found:
        raise ValueError(f"Nie odnaleziono nagłówka zadania {number} na stronie PDF {page.number+1}.")
    return min(item.y0 for item in found)


def line_html(spans: list[dict]) -> str:
    result = []
    for item in spans:
        text = item.get("text", "")
        if not text:
            continue
        value = html.escape(text, quote=False)
        font = item.get("font", "").lower()
        flags = item.get("flags", 0)
        if flags & 2 or "italic" in font or "oblique" in font:
            value = f"<em>{value}</em>"
        if flags & 16 or "bold" in font:
            value = f"<strong>{value}</strong>"
        result.append(value)
    return "".join(result).strip()


def extract_html(page: fitz.Page, y0: float, y1: float) -> str:
    # The source is a text PDF. Keep font-weight and style from original spans.
    data = page.get_text("dict", clip=fitz.Rect(60, y0, page.rect.width-48, y1), sort=True)
    chunks = []
    for block in sorted(data["blocks"], key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0])):
        if block.get("type") != 0:
            continue
        lines = []
        for line in block.get("lines", []):
            plain = "".join(sp.get("text", "") for sp in line.get("spans", [])).strip()
            if not plain or BOILERPLATE.fullmatch(plain) or NOISE.search(plain):
                continue
            rich = line_html(line.get("spans", []))
            if rich:
                lines.append(rich)
        if not lines:
            continue
        plain = re.sub(r"<[^>]*>", "", " ".join(lines))
        if len(plain.strip()) < 3:
            continue
        # Preserve the order and exact wording, while allowing responsive wrapping.
        rich_text = " ".join(lines)
        if plain.strip().startswith(("A.", "B.", "C.", "D.")):
            chunks.append(f'<p class="e8-original-option">{rich_text}</p>')
        else:
            chunks.append(f'<p class="e8-original-paragraph">{rich_text}</p>')
    return "\n".join(chunks)


def images_for_task(page: fitz.Page, number: int, top: float, bottom: float) -> str:
    if number not in (7, 9):
        return ""
    regions = []
    for img in page.get_images(full=True):
        try:
            rects = page.get_image_rects(img[0])
        except Exception:
            continue
        for rect in rects:
            if rect.y0 >= top and rect.y1 <= bottom and rect.width > 38 and rect.height > 25:
                regions.append(rect)
    if regions:
        box = fitz.Rect(
            min(r.x0 for r in regions)-8,
            min(r.y0 for r in regions)-8,
            max(r.x1 for r in regions)+8,
            max(r.y1 for r in regions)+8,
        )
    elif number == 9:
        # Photos are crucial to task 9. Fallback crop includes the full collage.
        box = fitz.Rect(72, 170, page.rect.width-65, 430)
    else:
        return ""
    box = box & page.rect
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"zadanie-{number}-ilustracje.png"
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=box, alpha=False)
    pix.save(IMAGE_DIR / name)
    return (f'<figure class="e8-original-figure"><img loading="lazy" '
            f'src="../../assets/opracowania/polski-2026/{name}" '
            f'alt="Ilustracje pochodzące z zadania {number} oryginalnego arkusza CKE">'
            '<figcaption>Ilustracje odtworzone z arkusza egzaminacyjnego.</figcaption></figure>')


def build(pdf_path: Path, guide_path: Path, dry_run: bool = False):
    if not pdf_path.exists():
        raise FileNotFoundError(f"Brak PDF: {pdf_path}")
    if not guide_path.exists():
        raise FileNotFoundError(f"Brak szablonu opracowania: {guide_path}")
    doc = fitz.open(pdf_path)
    if len(doc) < 16:
        raise ValueError("PDF ma mniej stron niż oczekiwane 16 stron części z zadaniami.")
    soup = BeautifulSoup(guide_path.read_text(encoding="utf-8"), "html.parser")

    for number, page_no in TASKS.items():
        page = doc[page_no]
        begin = task_marker(page, number)
        if number + 1 in TASKS and TASKS[number+1] == page_no:
            end = task_marker(page, number + 1) - 3
        else:
            end = page.rect.height - 42
        text = extract_html(page, begin-2, end)
        count = len(BeautifulSoup(text, "html.parser").get_text(" ",strip=True))
        if count < 70:
            raise ValueError(f"Zadanie {number}: ekstrakcja tekstu jest zbyt krótka ({count} znaków).")

        task_section = soup.find("section", id=f"zadanie-{number}")
        if task_section is None:
            raise ValueError(f"Brak zadania {number} w szablonie strony.")
        original = task_section.select_one(".e8-article-question")
        if original is None:
            raise ValueError(f"Brak miejsca na polecenie zadania {number}.")
        illustration = images_for_task(page, number, begin-2, end)
        supplemental = ""
        if number == 16:
            supplemental = ('<div class="e8-underline-example">'
                '<div><em>Kształt przyszłości zależy od <u>was</u>.</em>'
                '<p>Podkreślony wyraz w pierwszym zdaniu.</p></div>'
                '<div><em>Kształt <u>przyszłości</u> zależy od was.</em>'
                '<p>Podkreślony wyraz w drugim zdaniu.</p></div></div>')
        rendered = BeautifulSoup(
            '<div class="e8-article-question">'
            '<div class="e8-article-smalltitle">Pełne polecenie i wszystkie odpowiedzi — z arkusza CKE</div>'
            + text + illustration + supplemental + '</div>',
            "html.parser"
        )
        original.replace_with(rendered.div)

    # Complete literary/scientific source texts appear before their corresponding tasks.
    source_specs = [
        ("Stanisław Lem", "Przyjaciel Automateusza", 1,
         extract_html(doc[4], 95, doc[4].rect.height-38) +
         "\n" + extract_html(doc[5], 65, task_marker(doc[5], 1)-5)),
        ("Stephen Hawking", "Czy możemy kształtować naszą przyszłość?", 11,
         extract_html(doc[11], 95, doc[11].rect.height-40)),
    ]
    for author, title, first_task, content in source_specs:
        plain = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
        if len(plain.split()) < 220:
            raise ValueError(f"Niekompletny tekst źródłowy: {title} ({len(plain.split())} słów).")
        source = BeautifulSoup(
            f'<section class="e8-source-text" id="tekst-{first_task}">'
            '<div class="e8-article-smalltitle">Tekst źródłowy — pełny fragment z arkusza</div>'
            f'<h3>{html.escape(author)} · {html.escape(title)}</h3>'
            '<div class="e8-source-prose">' + content + '</div></section>',
            "html.parser"
        )
        first = soup.find("section", id=f"zadanie-{first_task}")
        first.insert_before(source.section)

    if dry_run:
        print("Poprawna ekstrakcja: 18 zadań, dwa teksty źródłowe.")
        return
    guide_path.write_text(str(soup)+"\n", encoding="utf-8")
    print(f"Wygenerowano pełny HTML: {guide_path} — 18 zadań i 2 teksty źródłowe.")


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--pdf", type=Path, default=SOURCE)
    cli.add_argument("--out", type=Path, default=GUIDE)
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    build(args.pdf, args.out, args.dry_run)
