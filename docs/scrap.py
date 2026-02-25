#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PDF_RE = re.compile(r"\.pdf($|\?)", re.IGNORECASE)
YEAR_RE = re.compile(r"(20\d{2})")  # 2000-2099

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EgzaminScraper/1.0; +https://example.invalid)"
}


@dataclass(frozen=True)
class SubjectConfig:
    key: str
    list_url: str


SUBJECTS: Dict[str, SubjectConfig] = {
    # Możesz dopisać kolejne listy jeśli masz inne kategorie
    "jezyk-polski": SubjectConfig(
        key="jezyk-polski",
        list_url="https://arkusze.pl/jezyk-polski-egzamin-osmoklasisty/",
    ),
    "matematyka": SubjectConfig(
        key="matematyka",
        list_url="https://arkusze.pl/matematyka-egzamin-osmoklasisty/",
    ),
    "jezyk-angielski": SubjectConfig(
        key="jezyk-angielski",
        list_url="https://arkusze.pl/jezyk-angielski-egzamin-osmoklasisty/",
    ),
}


def polite_sleep(base_delay: float, jitter: float) -> None:
    """Śpij między requestami, żeby nie młócić serwera."""
    if base_delay <= 0:
        return
    extra = random.uniform(0, jitter) if jitter > 0 else 0
    time.sleep(base_delay + extra)


def safe_filename(name: str) -> str:
    name = name.strip()
    # usuń dziwne znaki
    name = re.sub(r"[^\w\-.() ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "plik"


def extract_year(*texts: str) -> str:
    """Spróbuj znaleźć rocznik (YYYY) w URL/tytule/nazwie pliku."""
    for t in texts:
        if not t:
            continue
        m = YEAR_RE.search(t)
        if m:
            return m.group(1)
    return "unknown"


def request_get(session: requests.Session, url: str, timeout: int, retries: int,
                delay: float, jitter: float) -> requests.Response:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            polite_sleep(delay, jitter)
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < retries:
                # krótki backoff
                time.sleep(min(2.0 * attempt, 6.0))
            else:
                raise last_exc


def page_html(session: requests.Session, url: str, timeout: int, retries: int,
              delay: float, jitter: float) -> str:
    r = request_get(session, url, timeout, retries, delay, jitter)
    # arkusze.pl to zwykle utf-8; requests sam wykryje, ale zostawiamy fallback
    r.encoding = r.encoding or "utf-8"
    return r.text


def exam_pages_from_list_page(html: str, base_url: str) -> Tuple[Set[str], Optional[str]]:
    """Z jednej strony listy wyciąga linki do wpisów + link do następnej strony."""
    soup = BeautifulSoup(html, "html.parser")

    pages: Set[str] = set()

    # WordPress: nagłówki wpisów
    for a in soup.select("h2.entry-title a[href]"):
        href = a.get("href", "").strip()
        if href:
            pages.add(urljoin(base_url, href))

    # fallback: czasem h3 / inny układ
    if not pages:
        for a in soup.select("article a[href]"):
            href = a.get("href", "").strip()
            if href and "arkusze.pl/" in href and "egzamin" in href:
                pages.add(urljoin(base_url, href))

    # paginacja: "next"
    next_url = None
    next_a = soup.select_one("a.next[href]")
    if next_a:
        next_url = urljoin(base_url, next_a.get("href"))

    # czasem jest w nawigacji "Next page"
    if not next_url:
        for a in soup.select("a[href]"):
            txt = (a.get_text() or "").strip().lower()
            if txt in {"następna", "nastepna", "next"}:
                href = a.get("href", "").strip()
                if href and "/page/" in href:
                    next_url = urljoin(base_url, href)
                    break

    return pages, next_url


def crawl_list_all(session: requests.Session, start_url: str, timeout: int, retries: int,
                   delay: float, jitter: float, max_pages: int = 10_000) -> List[str]:
    """Przechodzi po /page/2/ /page/3/ itd. i zbiera wszystkie wpisy."""
    url = start_url
    all_pages: Set[str] = set()
    seen_list_pages: Set[str] = set()
    n = 0

    while url and url not in seen_list_pages and n < max_pages:
        seen_list_pages.add(url)
        n += 1

        html = page_html(session, url, timeout, retries, delay, jitter)
        pages, next_url = exam_pages_from_list_page(html, base_url=url)

        all_pages.update(pages)
        url = next_url

    return sorted(all_pages)


def pdf_links_from_exam_page(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: Set[str] = set()

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        if PDF_RE.search(full):
            links.add(full)

    return sorted(links)


def get_page_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    return title or ""


def download_pdf(session: requests.Session, pdf_url: str, out_path: Path, timeout: int,
                 retries: int, delay: float, jitter: float, min_bytes_ok: int = 1024) -> str:
    """
    Zapisuje PDF na dysk.
    Jeśli plik istnieje i wygląda OK, pomija.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        try:
            size = out_path.stat().st_size
            if size >= min_bytes_ok:
                return "skip_exists"
        except OSError:
            pass

    # download stream
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            polite_sleep(delay, jitter)
            with session.get(pdf_url, stream=True, timeout=timeout, allow_redirects=True) as r:
                r.raise_for_status()

                tmp_path = out_path.with_suffix(out_path.suffix + ".part")
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

                # sanity check
                if tmp_path.stat().st_size < min_bytes_ok:
                    tmp_path.unlink(missing_ok=True)
                    raise RuntimeError(f"Pobrany plik za mały: {tmp_path}")

                tmp_path.replace(out_path)
                return "downloaded"
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(min(2.0 * attempt, 6.0))
            else:
                raise last_exc
    raise last_exc  # pragma: no cover


def build_output_path(root: Path, subject: str, year: str, pdf_url: str) -> Path:
    filename = os.path.basename(urlparse(pdf_url).path) or "plik.pdf"
    filename = safe_filename(filename)
    return root / subject / year / filename


def load_manifest(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Scraper PDF-ów z arkusze.pl (ósmoklasista)")
    ap.add_argument("--out", default="pdf", help="Katalog wyjściowy (domyślnie: pdf)")
    ap.add_argument("--subjects", default="jezyk-polski,matematyka,jezyk-angielski",
                    help=f"Lista przedmiotów oddzielona przecinkami. Dostępne: {','.join(SUBJECTS.keys())}")
    ap.add_argument("--delay", type=float, default=1.2, help="Opóźnienie między requestami (sekundy)")
    ap.add_argument("--jitter", type=float, default=0.8, help="Losowy dodatek do delay (sekundy)")
    ap.add_argument("--timeout", type=int, default=30, help="Timeout requestów (sekundy)")
    ap.add_argument("--retries", type=int, default=3, help="Ile retry na request")
    ap.add_argument("--max-exams", type=int, default=10_000, help="Limit liczby stron egzaminów na przedmiot")
    args = ap.parse_args()

    out_root = Path(args.out)
    manifest_path = out_root / "manifest.json"
    manifest = load_manifest(manifest_path)
    manifest.setdefault("downloads", [])

    wanted = [s.strip() for s in args.subjects.split(",") if s.strip()]
    for s in wanted:
        if s not in SUBJECTS:
            raise SystemExit(f"Nieznany przedmiot: {s}. Dostępne: {', '.join(SUBJECTS.keys())}")

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    total_new = 0
    total_skipped = 0

    for subject in wanted:
        cfg = SUBJECTS[subject]
        print(f"\n== {subject} ==")
        exam_pages = crawl_list_all(
            session=session,
            start_url=cfg.list_url,
            timeout=args.timeout,
            retries=args.retries,
            delay=args.delay,
            jitter=args.jitter,
            max_pages=10_000,
        )
        if args.max_exams and len(exam_pages) > args.max_exams:
            exam_pages = exam_pages[: args.max_exams]

        print(f"Wpisów egzaminów znaleziono: {len(exam_pages)}")

        for idx, exam_url in enumerate(exam_pages, start=1):
            try:
                html = page_html(session, exam_url, args.timeout, args.retries, args.delay, args.jitter)
                title = get_page_title(html)
                pdfs = pdf_links_from_exam_page(html, exam_url)

                if not pdfs:
                    # czasem wpis bez pdf
                    continue

                for pdf_url in pdfs:
                    year = extract_year(pdf_url, exam_url, title)
                    out_path = build_output_path(out_root, subject, year, pdf_url)

                    status = download_pdf(
                        session=session,
                        pdf_url=pdf_url,
                        out_path=out_path,
                        timeout=args.timeout,
                        retries=args.retries,
                        delay=args.delay,
                        jitter=args.jitter,
                    )

                    if status == "downloaded":
                        total_new += 1
                        print(f"[{subject}] + {out_path}")
                    else:
                        total_skipped += 1

                    manifest["downloads"].append({
                        "subject": subject,
                        "year": year,
                        "exam_page": exam_url,
                        "title": title,
                        "pdf_url": pdf_url,
                        "file": str(out_path),
                        "status": status,
                        "ts": int(time.time()),
                    })

                # zapisuj manifest na bieżąco (odporność na przerwanie)
                save_manifest(manifest_path, manifest)

                if idx % 25 == 0:
                    print(f"Postęp {idx}/{len(exam_pages)}")

            except Exception as e:
                print(f"[{subject}] ERROR na {exam_url}: {e}")

    print(f"\nGotowe. Nowe pliki: {total_new}, pominięte (już były): {total_skipped}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()