from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


def _rect_to_list(r: fitz.Rect) -> list[float]:
    return [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]


def _now_iso() -> str:
    # Europe/Warsaw możesz dodać w projekcie, ale tu bez zależności:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def extract_layout_json(
    pdf_path: str,
    out_json_path: str,
    assets_dir: Optional[str] = None,
    extract_words: bool = True,
    extract_drawings: bool = True,
    extract_images: bool = True,
) -> dict:
    """
    Ekstraktuje 'layout JSON' z PDF:
    - tekst (blocks/lines/spans) z bbox i metadanymi fontów
    - opcjonalnie words z bbox
    - opcjonalnie drawings (linie/recty/krzywe) z bbox
    - opcjonalnie obrazy zapisane do assets_dir + bbox + ścieżka
    """
    doc = fitz.open(pdf_path)

    if assets_dir is None:
        assets_dir = os.path.join(os.path.dirname(out_json_path), "assets")
    os.makedirs(assets_dir, exist_ok=True)

    result: dict = {
        "meta": {
            "source_pdf": os.path.abspath(pdf_path),
            "page_count": doc.page_count,
            "created_at": _now_iso(),
            "extractor": {"name": "layout-extract-fitz", "version": "0.1"},
        },
        "pages": [],
    }

    for pi in range(doc.page_count):
        page = doc.load_page(pi)

        page_obj: dict = {
            "index": pi,
            "width": float(page.rect.width),
            "height": float(page.rect.height),
            "rotation": int(page.rotation or 0),
            "blocks": [],
        }

        # --- TEXT (dict) ---
        text_dict = page.get_text("dict")
        for b in text_dict.get("blocks", []):
            if b.get("type") != 0:
                # type 1 = image block w get_text("dict") (czasem), ale my obrazy bierzemy osobno
                continue

            block_rec: dict = {
                "type": "text_block",
                "bbox": b.get("bbox"),
                "lines": [],
            }

            for ln in b.get("lines", []):
                line_rec: dict = {
                    "bbox": ln.get("bbox"),
                    "spans": [],
                }
                for sp in ln.get("spans", []):
                    span_rec = {
                        "text": sp.get("text", ""),
                        "bbox": sp.get("bbox"),
                        "font": sp.get("font"),
                        "size": float(sp.get("size", 0.0)),
                        "flags": int(sp.get("flags", 0)),
                        "color": int(sp.get("color", 0)),
                        "origin": sp.get("origin"),  # [x, y] baseline
                    }
                    line_rec["spans"].append(span_rec)

                block_rec["lines"].append(line_rec)

            page_obj["blocks"].append(block_rec)

        # --- WORDS ---
        if extract_words:
            # words: [x0, y0, x1, y1, "word", block_no, line_no, word_no]
            for w in page.get_text("words"):
                x0, y0, x1, y1, txt, bno, lno, wno = w
                page_obj["blocks"].append(
                    {
                        "type": "word",
                        "text": txt,
                        "bbox": [float(x0), float(y0), float(x1), float(y1)],
                        "block_no": int(bno),
                        "line_no": int(lno),
                        "word_no": int(wno),
                    }
                )

        # --- DRAWINGS ---
        if extract_drawings:
            # get_drawings() zwraca listę dictów; itemy są surowe (line/rect/curve)
            for d in page.get_drawings():
                # bbox: fitz.Rect
                bbox = d.get("rect")
                stroke = d.get("color")  # może być int/tuple zależnie od wersji
                fill = d.get("fill")

                page_obj["blocks"].append(
                    {
                        "type": "drawing",
                        "bbox": _rect_to_list(bbox) if isinstance(bbox, fitz.Rect) else bbox,
                        "kind": "drawing",
                        "items": d.get("items", []),
                        "stroke": {
                            "color": stroke,
                            "width": d.get("width"),
                            "lineCap": d.get("lineCap"),
                            "lineJoin": d.get("lineJoin"),
                            "dashes": d.get("dashes"),
                        },
                        "fill": fill,
                    }
                )

        # --- IMAGES ---
        if extract_images:
            # page.get_images(full=True) -> list of tuples; xref jest kluczowy
            img_list = page.get_images(full=True)
            # Aby mieć bbox obrazów: page.get_image_rects(xref)
            img_idx = 0
            for img in img_list:
                xref = img[0]
                rects = page.get_image_rects(xref)
                if not rects:
                    continue

                # wyciągnij obraz jako pixmap (raz), zapisz
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                out_name = f"p{pi:03d}_img{img_idx:03d}_xref{xref}.png"
                out_path = os.path.join(assets_dir, out_name)
                pix.save(out_path)

                for r in rects:
                    page_obj["blocks"].append(
                        {
                            "type": "image",
                            "bbox": _rect_to_list(r),
                            "xref": int(xref),
                            "path": os.path.relpath(out_path, os.path.dirname(out_json_path)),
                            "width": int(pix.width),
                            "height": int(pix.height),
                        }
                    )

                img_idx += 1

        result["pages"].append(page_obj)

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    doc.close()
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="ścieżka do PDF")
    ap.add_argument("--out", default="layout.json", help="wyjściowy JSON")
    ap.add_argument("--assets", default=None, help="katalog na assets (obrazy)")
    args = ap.parse_args()

    extract_layout_json(args.pdf, args.out, assets_dir=args.assets)
    print(f"OK: zapisano {args.out}")