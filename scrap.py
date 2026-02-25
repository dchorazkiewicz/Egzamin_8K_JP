import os
import re
import time
import requests
from urllib.parse import urlparse, urlunparse, urljoin
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# ===== KONFIG =====
BASE = "https://arkusze.pl"
BASE_DOMAIN = "arkusze.pl"

OUTDIR = "pdf"
SLEEP = 0.25
OVERWRITE = False

SUBJECTS = [
    "jezyk-polski",
    "jezyk-angielski",
    "matematyka",
]

# Jeżeli chcesz mocniej przyspieszyć, zmniejsz SLEEP, ale ryzykujesz blokadę.
# ===== KONFIG END =====

YEAR_RE = re.compile(r"(19|20)\d{2}")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; arkusze-downloader/2.0)"
})

def canonicalize(url: str) -> str:
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Ujednolicamy scheme na https, czyścimy fragment
    return urlunparse(("https", netloc, p.path, p.params, p.query, ""))

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def get_text(url: str) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
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

    r = session.get(u, timeout=60)
    r.raise_for_status()

    existed = os.path.exists(path)
    with open(path, "wb") as f:
        f.write(r.content)

    if existed and OVERWRITE:
        return "OVERWRITE", path
    return "OK", path

def main():
    locs = collect_sitemap_locs()
    print("Sitemap URL-e łącznie:", len(locs))

    # Dodatkowo: od razu wyciągnij PDF-y jeśli jednak są w sitemap
    for subject in SUBJECTS:
        pdfs = set(u for u in locs if is_osmoklasisty_pdf(u, subject))

        # A jeśli nie ma PDF-ów w sitemap, to crawl stron z sitemap i wyciągnij z HTML
        candidate_pages = [u for u in locs if is_candidate_page(u, subject)]
        print(f"\n{subject}: strony do sprawdzenia:", len(candidate_pages))

        for i, page in enumerate(candidate_pages, 1):
            try:
                pdfs |= extract_pdf_links_from_page(page, subject)
            except Exception:
                pass

            if i % 200 == 0:
                print(f"{subject}: sprawdzono {i}/{len(candidate_pages)} stron, PDF-y: {len(pdfs)}")

            time.sleep(SLEEP)

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
            status, path = download_pdf(u, subject)
            print(status, os.path.relpath(path, OUTDIR))
            time.sleep(SLEEP)

if __name__ == "__main__":
    main()