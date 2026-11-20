#!/usr/bin/env python3
"""Uzupełnia archiwum E8 o brakujące oficjalne arkusze, odpowiedzi i transkrypcje.

Źródło: https://arkusze.pl/ — strony egzaminów dla każdego przedmiotu.
Domyślnie pobiera tylko rok 2026; istniejące pliki pozostawia bez zmian.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SUBJECTS = ("jezyk-polski", "matematyka", "jezyk-angielski")
EXAM_PAGE_TEMPLATES = (
    "https://arkusze.pl/egzamin-osmoklasisty-{subject}-{year}/",
    "https://arkusze.pl/egzamin-osmoklasisty-termin-dodatkowy-{subject}-{year}/",
    "https://arkusze.pl/egzamin-osmoklasisty-probny-{subject}-{year}/",
)
URL_PATH = re.compile(r"^/osmoklasisty/[^/]+\.pdf$", re.IGNORECASE)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Egzamin8K/2.0; education archive)"}


def get_pdf_urls(page: str, session: requests.Session, timeout: int) -> list[str]:
    response = session.get(page, timeout=timeout)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    urls = set()
    for a in soup.select("a[href]"):
        url = urljoin(page, a["href"])
        parsed = urlparse(url)
        if parsed.hostname not in {"arkusze.pl", "www.arkusze.pl"}:
            continue
        if URL_PATH.fullmatch(parsed.path):
            urls.add(url)
    return sorted(urls)


def sync(year: int, root: Path, delay: float, timeout: int, dry_run: bool) -> int:
    session = requests.Session()
    session.headers.update(HEADERS)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"downloads": []}
    known = {item.get("file"): item for item in manifest.get("downloads", [])}
    found = added = skipped = failures = 0
    for subject in SUBJECTS:
        for template in EXAM_PAGE_TEMPLATES:
            page = template.format(subject=subject, year=year)
            try:
                urls = get_pdf_urls(page, session, timeout)
            except requests.RequestException as exc:
                print(f"WARNING: nie pobrano listy {page}: {exc}", file=sys.stderr)
                failures += 1
                continue
            valid_urls = [url for url in urls if f"{subject}-{year}-" in urlparse(url).path]
            print(f"{subject} / {page.rsplit('/', 2)[-2]}: {len(valid_urls)} PDF")
            for url in valid_urls:
                found += 1
                name = Path(urlparse(url).path).name
                dest = root / subject / str(year) / name
                rel = dest.as_posix()
                if dest.exists() and dest.stat().st_size > 1024:
                    skipped += 1
                    continue
                if dry_run:
                    print(f"DRY-RUN + {rel} <- {url}")
                    continue
                try:
                    time.sleep(max(0, delay))
                    response = session.get(url, timeout=timeout)
                    response.raise_for_status()
                    content = response.content
                    if not content.startswith(b"%PDF-") or len(content) < 1024:
                        raise ValueError("nieprawidłowy PDF lub za mało danych")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    temp = dest.with_suffix(".pdf.tmp")
                    temp.write_bytes(content)
                    temp.replace(dest)
                    added += 1
                    known[rel] = {
                        "subject": subject,
                        "year": str(year),
                        "exam_page": page,
                        "title": name.removesuffix(".pdf"),
                        "pdf_url": url,
                        "file": rel,
                        "status": "downloaded",
                        "ts": int(time.time()),
                    }
                    print(f"+ {rel} ({len(content)} B)")
                except (requests.RequestException, OSError, ValueError) as exc:
                    failures += 1
                    print(f"ERROR {url}: {exc}", file=sys.stderr)
    if added:
        manifest["downloads"] = list(known.values())
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rok {year}: znaleziono {found} plików, dodano {added}, już było {skipped}, błędów {failures}")
    if failures:
        print("Niektóre źródła były niedostępne; ponowne uruchomienie może uzupełnić braki.", file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--out", type=Path, default=Path("docs/pdf"))
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--timeout", type=int, default=35)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 2017 <= args.year <= 2100:
        parser.error("nieprawidłowy rok")
    return sync(args.year, args.out, args.delay, args.timeout, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
