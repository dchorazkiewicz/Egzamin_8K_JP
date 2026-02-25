import os
import re
import time
import random
import socket
import requests
from urllib.parse import urlparse, urlunparse, urljoin
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# ===== KONFIG =====
BASE = "https://arkusze.pl"
BASE_DOMAIN = "arkusze.pl"

ROOTDIR = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(ROOTDIR, "pdf")
SLEEP = 1.2
OVERWRITE = False
LOG_EACH_PAGE = True
LOG_EACH_DOWNLOAD = True
LOG_SITEMAPS = False
LOG_ERRORS = True

SUBJECTS = [
    "jezyk-polski",
    "jezyk-angielski",
    "matematyka",
]

# Ręczne linki do PDF (jeśli chcesz pobrać coś niezależnie od sitemap/crawla).
DIRECT_PDFS: dict[str, list[str]] = {
    "jezyk-polski": [
        "https://arkusze.pl/osmoklasisty/jezyk-polski-2026-styczen-egzamin-osmoklasisty-probny.pdf",
    ],
}

# Jeżeli chcesz mocniej przyspieszyć, zmniejsz SLEEP, ale ryzykujesz blokadę.
# ===== KONFIG END =====

YEAR_RE = re.compile(r"(19|20)\d{2}")

session = requests.Session()
session.headers.update({
    # Używaj jawnego i uczciwego User-Agent; nie udawaj przeglądarki.
    "User-Agent": "arkusze-downloader/2.1 (educational)"
})

def check_dns_or_die(hostname: str) -> None:
    try:
        socket.getaddrinfo(hostname, 443)
    except OSError as e:
        raise RuntimeError(
            f"DNS: nie mogę rozwiązać nazwy {hostname!r} ({e}). "
            "Sprawdź połączenie z internetem/DNS i spróbuj ponownie."
        )

def sleep_polite(base_seconds: float) -> None:
    # Mały jitter ogranicza "burst" i jest bardziej przyjazny dla serwera.
    jitter = base_seconds * 0.25
    time.sleep(max(0.0, random.uniform(base_seconds - jitter, base_seconds + jitter)))

def canonicalize(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Ujednolicamy scheme na https, czyścimy fragment
    return urlunparse(("https", netloc, p.path, p.params, p.query, ""))

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def get_with_retries(url: str, *, timeout: int, max_tries: int = 4) -> requests.Response:
    """
    Pobierz URL w sposób "grzeczny":
    - ograniczona liczba prób
    - backoff dla 429/5xx
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_tries + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = min(30, 2 ** attempt)
                if LOG_ERRORS:
                    print("RETRY", r.status_code, url, "sleep", f"{wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < max_tries:
                wait = min(30, 2 ** attempt)
                if LOG_ERRORS:
                    print("RETRY EXC", url, "sleep", f"{wait}s", repr(e))
                time.sleep(wait)
            else:
                break
    assert last_exc is not None
    raise last_exc

def get_text(url: str) -> str:
    r = get_with_retries(url, timeout=30)
    return r.text

def is_arkusze_host(url: str) -> bool:
    p = urlparse(canonicalize(url))
    return p.netloc.endswith(BASE_DOMAIN)

def extract_year(s: str) -> str:
    m = YEAR_RE.search(s)
    return m.group(0) if m else "unknown"

def try_parse_sitemap(url: str) -> set[str]:
    try:
        xml_text = get_text(url)
    except Exception:
        return set()

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return set()

    locs = set()
    for elem in root.iter():
        if elem.tag.endswith("loc") and elem.text:
            locs.add(canonicalize(elem.text.strip()))
    return locs

def collect_all_sitemap_urls() -> set[str]:
    candidates = [
        BASE + "/robots.txt",
        BASE + "/sitemap_index.xml",
        BASE + "/sitemap.xml",
        BASE + "/wp-sitemap.xml",
    ]

    sitemap_urls = set()

    # robots.txt -> linie Sitemap:
    try:
        robots = get_text(candidates[0])
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_urls.add(line.split(":", 1)[1].strip())
    except Exception:
        pass

    sitemap_urls.update(candidates[1:])
    return {canonicalize(u) for u in sitemap_urls}

def collect_sitemap_locs() -> set[str]:
    sitemap_urls = collect_all_sitemap_urls()

    all_locs = set()
    queue = list(sitemap_urls)
    seen = set()

    while queue:
        sm_url = canonicalize(queue.pop())
        if sm_url in seen:
            continue
        seen.add(sm_url)

        if LOG_SITEMAPS:
            print("SITEMAP:", sm_url)

        locs = try_parse_sitemap(sm_url)
        if not locs:
            continue

        for loc in locs:
            if loc.lower().endswith(".xml") and "sitemap" in loc.lower():
                queue.append(loc)
            else:
                all_locs.add(loc)

        time.sleep(SLEEP)

    return all_locs

def is_osmoklasisty_pdf(url: str, subject_slug: str) -> bool:
    u = canonicalize(url)
    p = urlparse(u)
    if not p.netloc.endswith(BASE_DOMAIN):
        return False
    path = p.path.lower()
    return (
        path.startswith("/osmoklasisty/")
        and path.endswith(".pdf")
        and subject_slug.lower() in path
    )

def is_candidate_page(url: str, subject_slug: str) -> bool:
    """
    Strona HTML, która potencjalnie linkuje PDF-y.
    Bierzemy takie, które zawierają subject w URL lub mają w URL 'osmoklasisty'.
    """
    u = canonicalize(url)
    p = urlparse(u)

    if not p.netloc.endswith(BASE_DOMAIN):
        return False

    path = p.path.lower()
    if path.endswith(".pdf"):
        return False

    return (subject_slug.lower() in path) or ("osmoklasisty" in path)

def extract_pdf_links_from_page(page_url: str, subject_slug: str) -> set[str]:
    html = get_text(page_url)
    soup = BeautifulSoup(html, "html.parser")

    found = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = canonicalize(urljoin(page_url, href))
        if is_osmoklasisty_pdf(abs_url, subject_slug):
            found.add(abs_url)
    return found

def target_path(pdf_url: str, subject_slug: str) -> str:
    u = canonicalize(pdf_url)
    filename = u.split("/")[-1]
    year = extract_year(u)
    return os.path.join(OUTDIR, subject_slug, year, filename)

def download_pdf(pdf_url: str, subject_slug: str) -> tuple[str, str]:
    u = canonicalize(pdf_url)
    path = target_path(u, subject_slug)
    ensure_dir(os.path.dirname(path))

    if os.path.exists(path) and not OVERWRITE:
        return "SKIP", path

    r = get_with_retries(u, timeout=60)

    content_type = (r.headers.get("Content-Type") or "").lower()
    if "pdf" not in content_type and LOG_ERRORS:
        # Czasem serwery zwracają HTML (np. 403/anty-bot) mimo linku .pdf.
        print("WARN non-pdf Content-Type:", content_type or "missing", "for", u)

    existed = os.path.exists(path)
    with open(path, "wb") as f:
        f.write(r.content)

    if existed and OVERWRITE:
        return "OVERWRITE", path
    return "OK", path

def main():
    print("OUTDIR:", OUTDIR)
    try:
        check_dns_or_die(BASE_DOMAIN)
    except Exception as e:
        print("ERROR", e)
        return

    # Szybko pobierz ręcznie podane PDF-y (nie czekaj na sitemap/crawl).
    for subject in SUBJECTS:
        direct = []
        for u in DIRECT_PDFS.get(subject, []):
            u = canonicalize(u)
            if is_osmoklasisty_pdf(u, subject):
                direct.append(u)
            elif LOG_ERRORS:
                print("WARN direct URL nie pasuje do filtra PDF:", u)

        direct = sorted(set(direct))
        if not direct:
            continue

        print(f"\n{subject}: direct PDF-y:", len(direct))
        for u in direct:
            if LOG_EACH_DOWNLOAD:
                dest = target_path(u, subject)
                rel_dest = os.path.relpath(dest, OUTDIR)
                if os.path.exists(dest) and not OVERWRITE:
                    print("PLAN SKIP", u, "->", rel_dest)
                else:
                    print("PLAN GET ", u, "->", rel_dest)
            try:
                status, path = download_pdf(u, subject)
                print(status, os.path.relpath(path, OUTDIR))
            except requests.HTTPError as e:
                if LOG_ERRORS:
                    code = getattr(getattr(e, "response", None), "status_code", None)
                    print("ERROR GET", u, "HTTP", code, e)
            except Exception as e:
                if LOG_ERRORS:
                    print("ERROR GET", u, repr(e))
            sleep_polite(SLEEP)

    locs = collect_sitemap_locs()
    print("Sitemap URL-e łącznie:", len(locs))

    # Dodatkowo: od razu wyciągnij PDF-y jeśli jednak są w sitemap
    for subject in SUBJECTS:
        pdfs = set(u for u in locs if is_osmoklasisty_pdf(u, subject))

        # Dołóż ręcznie podane PDF-y
        for u in DIRECT_PDFS.get(subject, []):
            u = canonicalize(u)
            if is_osmoklasisty_pdf(u, subject):
                pdfs.add(u)
            elif LOG_ERRORS:
                print("WARN direct URL nie pasuje do filtra PDF:", u)

        # A jeśli nie ma PDF-ów w sitemap, to crawl stron z sitemap i wyciągnij z HTML
        candidate_pages = [u for u in locs if is_candidate_page(u, subject)]
        print(f"\n{subject}: strony do sprawdzenia:", len(candidate_pages))

        for i, page in enumerate(candidate_pages, 1):
            if LOG_EACH_PAGE:
                print(f"{subject}: CHECK {i}/{len(candidate_pages)} {page}")
            try:
                pdfs |= extract_pdf_links_from_page(page, subject)
            except Exception as e:
                if LOG_ERRORS:
                    print(f"{subject}: ERROR page {page}: {e!r}")

            if i % 200 == 0:
                print(f"{subject}: sprawdzono {i}/{len(candidate_pages)} stron, PDF-y: {len(pdfs)}")

            sleep_polite(SLEEP)

        pdfs = sorted(pdfs)
        print(f"{subject}: PDF-y znalezione:", len(pdfs))

        # manifest per przedmiot
        manifest_dir = os.path.join(OUTDIR, subject)
        ensure_dir(manifest_dir)
        manifest_path = os.path.join(manifest_dir, "manifest.txt")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("\n".join(pdfs) + "\n")

        # download
        for u in pdfs:
            if LOG_EACH_DOWNLOAD:
                dest = target_path(u, subject)
                rel_dest = os.path.relpath(dest, OUTDIR)
                if os.path.exists(dest) and not OVERWRITE:
                    print("PLAN SKIP", u, "->", rel_dest)
                else:
                    print("PLAN GET ", u, "->", rel_dest)
            try:
                status, path = download_pdf(u, subject)
                print(status, os.path.relpath(path, OUTDIR))
            except requests.HTTPError as e:
                if LOG_ERRORS:
                    code = getattr(getattr(e, "response", None), "status_code", None)
                    print("ERROR GET", u, "HTTP", code, e)
            except Exception as e:
                if LOG_ERRORS:
                    print("ERROR GET", u, repr(e))
            sleep_polite(SLEEP)

if __name__ == "__main__":
    main()
