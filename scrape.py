"""
scrape.py — Tasks 2 / 3 / 4
Fetches Doug Scott's slot canyon catalog (dougscottart.com), parses GPS coords
and ACA ratings from each canyon's "beta facts" section, and writes
data/canyons.csv.  Raw HTML is cached in data/raw/ so you can reparse without
re-fetching.  Parse failures are logged to parse_errors.log.

Usage:
    pip install -r requirements.txt
    python scrape.py

After running, manually review data/canyons.csv and parse_errors.log (Task 5).
"""

import csv
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAIN_URL   = "https://www.dougscottart.com/hobbies/canyons/canyons.htm"
BASE_URL   = "https://www.dougscottart.com"
DATA_DIR   = Path("data")
RAW_DIR    = DATA_DIR / "raw"
CSV_PATH   = DATA_DIR / "canyons.csv"
LOG_PATH   = Path("parse_errors.log")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    )
}

# Polite crawl delay between subpage requests (seconds)
CRAWL_DELAY = 1.0

# US Southwest sanity bounds for decimal-degree validation
LAT_MIN, LAT_MAX =  25.0,  50.0
LON_MIN, LON_MAX = -125.0, -100.0

CSV_FIELDS = [
    "name", "url", "lat", "lon",
    "aca_rating", "aca_technical", "aca_water", "aca_commitment",
    "region", "coord_raw", "coord_source", "notes", "exclude",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

error_log = logging.getLogger("parse_errors")
error_log.setLevel(logging.WARNING)
_fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(message)s"))
error_log.addHandler(_fh)

# ---------------------------------------------------------------------------
# Coordinate parsing  (Tasks 3 & 4)
# ---------------------------------------------------------------------------

_DEG  = "[°˚º◦ᵒ]"
_MIN  = "['''′`´]"
_HEMI = "[NSEWnsew]"

# Two alternatives so that a suffix hemisphere (with optional space before it)
# is captured without accidentally stealing the prefix of the next coordinate.
# Alt-1 matches a coord that ends with an explicit suffix hemi NOT followed by
# a digit.  Alt-2 is the fallback for prefix-hemi or bare coords.
_COORD_RE = re.compile(
    rf"(?P<hp>{_HEMI})?\s*(?P<deg>\d{{1,3}}){_DEG}\s*(?P<min>\d+(?:\.\d+)?){_MIN}?\s?(?P<hs>{_HEMI})(?!\d)"
    r"|"
    rf"(?P<hp2>{_HEMI})?\s*(?P<deg2>\d{{1,3}}){_DEG}\s*(?P<min2>\d+(?:\.\d+)?){_MIN}?",
    re.UNICODE,
)


def _dm_to_dd(deg: str, mn: str, hemi: str) -> float:
    dd = int(deg) + float(mn) / 60
    if hemi.upper() in ("S", "W"):
        dd = -dd
    return round(dd, 6)


def parse_coords(raw: str) -> tuple[float | None, float | None]:
    """
    Extract the first lat/lon pair from a raw GPS string.
    Returns (lat, lon) in decimal degrees, or (None, None) on failure.
    Handles 'down to' range syntax by taking the first (upper) coord.
    """
    coords: list[tuple[str, float]] = []
    for m in _COORD_RE.finditer(raw):
        if m.group("deg") is not None:
            hemi = (m.group("hp") or m.group("hs") or "").upper()
            coords.append((hemi, _dm_to_dd(m.group("deg"), m.group("min"), hemi)))
        else:
            hemi = (m.group("hp2") or "").upper()
            coords.append((hemi, _dm_to_dd(m.group("deg2"), m.group("min2"), hemi)))

    lats = [dd for h, dd in coords if h in ("N", "S")]
    lons = [dd for h, dd in coords if h in ("E", "W")]
    if lats and lons:
        return lats[0], lons[0]
    return None, None


def validate_coords(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX

# ---------------------------------------------------------------------------
# ACA rating parsing  (Task 3)
# ---------------------------------------------------------------------------

# Matches patterns like:  3B III  /  3B/III  /  3bIII  /  2A II+
_ACA_RE = re.compile(
    r"(?P<technical>[1-4][ABC])\s*[/\-]?\s*(?P<commitment>I{1,3}V?|V?I{0,3})(?P<mod>[+\-]?)",
    re.IGNORECASE,
)
# Water rating sometimes appears separately: "water: III" or embedded
_WATER_RE = re.compile(r"water\s*[:\-]?\s*(I{1,3}V?|V?I{0,3}[+\-]?)", re.IGNORECASE)


def parse_aca(text: str) -> dict:
    """Return dict with aca_rating, aca_technical, aca_water, aca_commitment."""
    result = {
        "aca_rating": "",
        "aca_technical": "",
        "aca_water": "",
        "aca_commitment": "",
    }
    m = _ACA_RE.search(text)
    if m:
        tech = m.group("technical").upper()
        commit = (m.group("commitment") + m.group("mod")).upper()
        result["aca_technical"] = tech
        result["aca_commitment"] = commit
        result["aca_rating"] = f"{tech} {commit}".strip()

    wm = _WATER_RE.search(text)
    if wm:
        result["aca_water"] = wm.group(1).upper()

    return result

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update(HEADERS)


def fetch(url: str, cache_path: Path | None = None) -> str | None:
    """
    Fetch URL as text (UTF-8 with replacement).  If cache_path exists, use it.
    Saves raw HTML to cache_path when provided.
    """
    if cache_path and cache_path.exists():
        log.debug("Cache hit: %s", cache_path.name)
        return cache_path.read_text(encoding="utf-8", errors="replace")

    try:
        resp = _session.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Fetch failed for %s: %s", url, exc)
        return None

    # Try the declared encoding first; fall back to windows-1252 (common on
    # older personal sites), then force UTF-8 with replacement chars.
    enc = resp.encoding or "utf-8"
    try:
        text = resp.content.decode(enc)
    except (UnicodeDecodeError, LookupError):
        try:
            text = resp.content.decode("windows-1252")
        except UnicodeDecodeError:
            text = resp.content.decode("utf-8", errors="replace")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")

    return text

# ---------------------------------------------------------------------------
# Subpage slug → cache filename
# ---------------------------------------------------------------------------

def _slug(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return re.sub(r"[^\w\-]", "_", path.split("/")[-1]) or "index"

# ---------------------------------------------------------------------------
# Task 2 — Main page scrape + subpage discovery
# ---------------------------------------------------------------------------

def discover_canyons(html: str) -> list[dict]:
    """
    Parse the main catalog page and return a list of
    {'name': str, 'url': str} dicts for each canyon subpage link.
    """
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        text: str = a.get_text(strip=True)

        if not text or not href:
            continue

        # Resolve relative URLs
        abs_url = urljoin(MAIN_URL, href)

        # Keep only links that live within the canyons section of the site
        parsed = urlparse(abs_url)
        if parsed.netloc not in ("www.dougscottart.com", "dougscottart.com"):
            continue
        if "/canyons/" not in parsed.path and "/canyon" not in parsed.path.lower():
            continue
        # Skip the main catalog page itself and bare section anchors
        if abs_url.split("#")[0] == MAIN_URL.split("#")[0]:
            continue
        if not parsed.path.endswith((".htm", ".html")):
            continue

        if abs_url in seen:
            continue
        seen.add(abs_url)

        entries.append({"name": text, "url": abs_url})

    return entries

# ---------------------------------------------------------------------------
# Task 3 — Subpage scraper + beta facts parser
# ---------------------------------------------------------------------------

# Headings that introduce the beta-facts block (case-insensitive)
_BETA_HEADINGS = re.compile(
    r"beta\s*facts?|technical\s*info|canyon\s*info|details|description",
    re.IGNORECASE,
)


def _find_beta_block(soup: BeautifulSoup) -> str:
    """
    Locate the beta-facts section in a subpage and return its text.
    Falls back to full-page text if no dedicated section is found.
    """
    # Strategy 1: look for a heading that matches beta-facts keywords
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "b", "strong"]):
        if _BETA_HEADINGS.search(tag.get_text()):
            # Collect text from siblings/parent until next heading
            block_parts = []
            for sibling in tag.next_siblings:
                if sibling.name in ("h1", "h2", "h3", "h4"):
                    break
                if hasattr(sibling, "get_text"):
                    block_parts.append(sibling.get_text(" ", strip=True))
                elif isinstance(sibling, str):
                    block_parts.append(sibling)
            candidate = " ".join(block_parts)
            if candidate.strip():
                return candidate

    # Strategy 2: look for a table row or paragraph containing GPS-like text
    page_text = soup.get_text(" ", strip=True)
    return page_text


def scrape_subpage(name: str, url: str) -> dict:
    """
    Fetch a canyon subpage and extract all available fields.
    Returns a row dict matching CSV_FIELDS.
    """
    row: dict = {f: "" for f in CSV_FIELDS}
    row["name"] = name
    row["url"] = url
    row["coord_source"] = "none"
    row["exclude"] = "false"

    slug = _slug(url)
    cache_path = RAW_DIR / f"{slug}.html"

    html = fetch(url, cache_path=cache_path)
    if html is None:
        error_log.warning("FETCH_ERROR | %s | %s", url, name)
        return row

    soup = BeautifulSoup(html, "lxml")
    beta_text = _find_beta_block(soup)

    # --- ACA rating ---
    aca = parse_aca(beta_text)
    row.update(aca)

    # --- GPS coords ---
    # Search for a GPS label followed by coordinate text
    gps_pattern = re.compile(
        r"(?:GPS|coordinates?|location|lat\.?|N\s*\d{2})[^\n]{0,200}",
        re.IGNORECASE,
    )
    gps_candidates = gps_pattern.findall(beta_text)
    raw_coord = ""
    lat, lon = None, None

    for candidate in gps_candidates:
        lat, lon = parse_coords(candidate)
        if lat is not None:
            raw_coord = candidate.strip()[:200]
            break

    # Fallback: scan full page text for any coordinate pair
    if lat is None:
        full_text = soup.get_text(" ", strip=True)
        lat, lon = parse_coords(full_text)
        if lat is not None:
            raw_coord = f"[full-page fallback] {full_text[:100]}"

    if lat is not None and lon is not None:
        if validate_coords(lat, lon):
            row["lat"] = lat
            row["lon"] = lon
            row["coord_raw"] = raw_coord
            row["coord_source"] = "scraped"
        else:
            error_log.warning(
                "COORD_OUT_OF_RANGE | %s | %s | lat=%s lon=%s",
                url, name, lat, lon
            )
            row["coord_raw"] = raw_coord
    else:
        error_log.warning("COORD_PARSE_FAIL | %s | %s | raw=%r", url, name, raw_coord or beta_text[:120])

    # --- Region: try to infer from URL path or page title ---
    title_tag = soup.find("title")
    row["region"] = title_tag.get_text(strip=True) if title_tag else ""

    return row

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)

    log.info("Fetching main catalog page: %s", MAIN_URL)
    main_cache = RAW_DIR / "main_catalog.html"
    html = fetch(MAIN_URL, cache_path=main_cache)
    if html is None:
        log.error("Could not fetch main page. Aborting.")
        sys.exit(1)

    # --- Task 2: discover subpages ---
    entries = discover_canyons(html)
    log.info("Discovered %d canyon subpage links", len(entries))
    log.info("First 5:")
    for e in entries[:5]:
        log.info("  %s  |  %s", e["name"], e["url"])

    if not entries:
        log.error("No canyon links found — check MAIN_URL or site structure.")
        sys.exit(1)

    # --- Tasks 3 & 4: scrape subpages, parse coords + ACA ---
    rows: list[dict] = []
    n_coords   = 0
    n_aca      = 0
    n_failures = 0

    for i, entry in enumerate(entries, 1):
        log.info("[%d/%d] Scraping: %s", i, len(entries), entry["name"])
        row = scrape_subpage(entry["name"], entry["url"])
        rows.append(row)

        if row["lat"]:
            n_coords += 1
        else:
            n_failures += 1

        if row["aca_rating"]:
            n_aca += 1

        if i < len(entries):
            time.sleep(CRAWL_DELAY)

    # --- Task 4: write CSV ---
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    log.info("")
    log.info("=== Summary ===")
    log.info("Total canyons   : %d", len(rows))
    log.info("Coords parsed   : %d", n_coords)
    log.info("Parse failures  : %d (see %s)", n_failures, LOG_PATH)
    log.info("ACA ratings found: %d  missing: %d", n_aca, len(rows) - n_aca)
    log.info("CSV written to  : %s", CSV_PATH)


if __name__ == "__main__":
    main()
