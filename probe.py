import argparse
import sys
import socket
from urllib.parse import urlparse, urlunparse

import requests


def canonicalize(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return urlunparse((p.scheme or "https", netloc, p.path, p.params, p.query, ""))


def fetch(session: requests.Session, url: str, timeout: int) -> None:
    url = canonicalize(url)
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:
        print("ERROR", url, repr(e))
        return

    final_url = canonicalize(r.url)
    content_type = (r.headers.get("Content-Type") or "").lower()
    size = r.headers.get("Content-Length") or "unknown"
    first_bytes = r.content[:8]
    is_pdf_sig = first_bytes.startswith(b"%PDF-")

    print("URL     :", url)
    print("STATUS  :", r.status_code)
    if final_url != url:
        print("FINAL   :", final_url)
    if "retry-after" in {k.lower() for k in r.headers.keys()}:
        print("RETRY-AF:", r.headers.get("Retry-After"))
    print("TYPE    :", content_type or "missing")
    print("LENGTH  :", size)
    print("PDF-SIG :", "yes" if is_pdf_sig else "no")
    if r.status_code >= 400 and r.text:
        snippet = r.text[:200].replace("\n", "\\n")
        print("BODY200 :", snippet)
    print("-" * 60)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Prosty test dostępu do URL-i (status, Content-Type, sygnatura PDF)."
    )
    ap.add_argument("urls", nargs="*", help="URL-e do sprawdzenia (jak puste, użyje domyślnego)")
    ap.add_argument("--timeout", type=int, default=30, help="Timeout w sekundach")
    args = ap.parse_args(argv)

    session = requests.Session()
    # Jawny, uczciwy User-Agent (bez udawania przeglądarki).
    session.headers.update({"User-Agent": "Egzamin_8K_JP-probe/1.0"})

    urls = args.urls or [
        "https://arkusze.pl/osmoklasisty/jezyk-polski-2026-styczen-egzamin-osmoklasisty-probny.pdf"
    ]

    # Szybki check DNS, żeby błąd był czytelny.
    host = urlparse(canonicalize(urls[0])).netloc
    try:
        socket.getaddrinfo(host, 443)
    except OSError as e:
        print(
            "ERROR DNS: nie mogę rozwiązać nazwy",
            repr(host),
            "- sprawdź internet/DNS i spróbuj ponownie.",
            repr(e),
        )
        return 2

    for u in urls:
        fetch(session, u, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
