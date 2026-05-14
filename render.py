"""
render.py — Tasks 6 & 7
Reads data/canyons.csv (after manual review), generates:
  output/map.html   — filterable Leaflet.js planning map
  output/canyons.gpx — GPX waypoint file for GAIA GPS import

Usage:
    python render.py

Skips rows where exclude=true or lat/lon are empty.
"""

import csv
import html as html_mod
import json
from pathlib import Path

import gpxpy
import gpxpy.gpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CSV_PATH  = Path("data/canyons.csv")
MAP_PATH  = Path("output/map.html")
GPX_PATH  = Path("output/canyons.gpx")

# ---------------------------------------------------------------------------
# Load CSV
# ---------------------------------------------------------------------------

def load_canyons(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("exclude", "").strip().lower() == "true":
                continue
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (ValueError, KeyError):
                continue
            rows.append({
                "name":           row.get("name", "").strip(),
                "url":            row.get("url", "").strip(),
                "lat":            lat,
                "lon":            lon,
                "aca_rating":     row.get("aca_rating", "").strip(),
                "aca_technical":  row.get("aca_technical", "").strip(),
                "aca_water":      row.get("aca_water", "").strip(),
                "aca_commitment": row.get("aca_commitment", "").strip(),
                "region":         row.get("region", "").strip(),
                "notes":          row.get("notes", "").strip(),
            })
    return rows

# ---------------------------------------------------------------------------
# Task 7 — GPX export
# ---------------------------------------------------------------------------

def write_gpx(canyons: list[dict], out_path: Path) -> None:
    gpx = gpxpy.gpx.GPX()
    gpx.name = "Doug Scott Slot Canyons"
    gpx.description = "Canyon waypoints scraped from dougscottart.com"

    for c in canyons:
        wpt = gpxpy.gpx.GPXWaypoint(
            latitude=c["lat"],
            longitude=c["lon"],
            name=c["name"],
        )
        rating = c["aca_rating"] or "unrated"
        wpt.description = f"ACA: {rating} | {c['url']}"
        wpt.comment = c["region"] or ""
        gpx.waypoints.append(wpt)

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(gpx.to_xml(), encoding="utf-8")
    print(f"GPX written: {out_path}  ({len(canyons)} waypoints)")

# ---------------------------------------------------------------------------
# Task 6 — Leaflet.js map HTML
# ---------------------------------------------------------------------------

def write_map(canyons: list[dict], out_path: Path) -> None:
    # Collect unique technical and commitment ratings for filter checkboxes
    tech_ratings   = sorted({c["aca_technical"]   for c in canyons if c["aca_technical"]},
                            key=lambda x: (x[0], x[1:]))
    commit_ratings = sorted({c["aca_commitment"]  for c in canyons if c["aca_commitment"]},
                            key=lambda x: (len(x), x))

    markers_json = json.dumps(canyons, ensure_ascii=False)

    def checkbox_block(label: str, values: list[str], group: str) -> str:
        if not values:
            return ""
        items = "\n".join(
            f'          <label><input type="checkbox" class="filter-cb" data-group="{group}" '
            f'value="{html_mod.escape(v)}" checked> {html_mod.escape(v)}</label>'
            for v in values
        )
        return f"""
        <div class="filter-group">
          <div class="filter-label">{label}</div>
{items}
        </div>"""

    tech_checkboxes   = checkbox_block("Technical", tech_ratings, "technical")
    commit_checkboxes = checkbox_block("Commitment", commit_ratings, "commitment")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Doug Scott Slot Canyons</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <!-- Leaflet core -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <!-- MarkerCluster -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />

  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{ display: flex; height: 100vh; font-family: system-ui, sans-serif; font-size: 14px; }}

    /* ── Sidebar ── */
    #sidebar {{
      width: 240px;
      min-width: 200px;
      background: #1a1a2e;
      color: #e0e0e0;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 12px;
      gap: 12px;
      z-index: 1000;
    }}
    #sidebar h1 {{ font-size: 15px; color: #a8d5ba; line-height: 1.3; }}
    #sidebar h1 small {{ display: block; font-size: 11px; color: #888; margin-top: 2px; }}

    #search-box {{
      width: 100%;
      padding: 6px 8px;
      border-radius: 4px;
      border: 1px solid #444;
      background: #111;
      color: #eee;
      font-size: 13px;
    }}
    #search-box::placeholder {{ color: #666; }}

    .filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
    .filter-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                     letter-spacing: .06em; color: #888; margin-bottom: 2px; }}
    .filter-group label {{ display: flex; align-items: center; gap: 6px;
                           font-size: 13px; cursor: pointer; }}
    .filter-group input[type=checkbox] {{ accent-color: #a8d5ba; }}

    #badge {{
      display: inline-block;
      background: #a8d5ba;
      color: #1a1a2e;
      font-size: 11px;
      font-weight: 700;
      padding: 1px 7px;
      border-radius: 10px;
    }}
    #reset-btn {{
      padding: 6px;
      background: #333;
      color: #ccc;
      border: 1px solid #555;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }}
    #reset-btn:hover {{ background: #444; }}

    #status-bar {{ font-size: 11px; color: #666; }}

    /* ── Map ── */
    #map {{ flex: 1; }}

    /* ── Popup ── */
    .canyon-popup {{ font-size: 13px; line-height: 1.5; min-width: 180px; }}
    .canyon-popup strong {{ font-size: 14px; color: #1a1a2e; }}
    .canyon-popup .aca {{ color: #555; margin: 2px 0; }}
    .canyon-popup a {{ color: #2a7a5a; text-decoration: none; }}
    .canyon-popup a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>

<div id="sidebar">
  <h1>Slot Canyons
    <small>Doug Scott's catalog</small>
  </h1>

  <input id="search-box" type="search" placeholder="Search canyon name…" />

  <div>
    <span id="badge">0</span> visible
  </div>

  {tech_checkboxes}
  {commit_checkboxes}

  <button id="reset-btn">Reset filters</button>
  <div id="status-bar"></div>
</div>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
// ── Data ──────────────────────────────────────────────────────────────────
const CANYONS = {markers_json};

// ── Map init ──────────────────────────────────────────────────────────────
const map = L.map('map').setView([36.5, -111.5], 7);

L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 17,
  attribution:
    'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ' +
    '<a href="http://viewfinderpanoramas.org">SRTM</a> | ' +
    'Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> ' +
    '(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
}}).addTo(map);

// ── Cluster layer ─────────────────────────────────────────────────────────
const cluster = L.markerClusterGroup({{ chunkedLoading: true }});
map.addLayer(cluster);

// ── Build markers ─────────────────────────────────────────────────────────
function popupHtml(c) {{
  const aca   = c.aca_rating  ? `<div class="aca">ACA: ${{c.aca_rating}}</div>` : '';
  const water = c.aca_water   ? `<div class="aca">Water: ${{c.aca_water}}</div>` : '';
  const region = c.region     ? `<div class="aca">Region: ${{c.region}}</div>` : '';
  const notes  = c.notes      ? `<div class="aca">${{c.notes}}</div>` : '';
  const link   = c.url        ? `<a href="${{c.url}}" target="_blank" rel="noopener">Doug's page ↗</a>` : '';
  return `<div class="canyon-popup">
    <strong>${{c.name}}</strong>
    ${{aca}}${{water}}${{region}}${{notes}}
    ${{link}}
  </div>`;
}}

const markers = CANYONS.map(c => {{
  const m = L.marker([c.lat, c.lon]);
  m.bindPopup(popupHtml(c));
  m._canyonData = c;
  return m;
}});

// ── Filter logic ──────────────────────────────────────────────────────────
function activeFilters() {{
  const techChecked   = new Set();
  const commitChecked = new Set();
  document.querySelectorAll('.filter-cb[data-group="technical"]:checked').forEach(
    cb => techChecked.add(cb.value)
  );
  document.querySelectorAll('.filter-cb[data-group="commitment"]:checked').forEach(
    cb => commitChecked.add(cb.value)
  );
  const searchTerm = document.getElementById('search-box').value.trim().toLowerCase();
  return {{ techChecked, commitChecked, searchTerm }};
}}

function applyFilters() {{
  const {{ techChecked, commitChecked, searchTerm }} = activeFilters();
  const hasTechFilter   = techChecked.size   > 0;
  const hasCommitFilter = commitChecked.size > 0;
  let visible = 0;

  cluster.clearLayers();
  const toAdd = [];

  markers.forEach(m => {{
    const c = m._canyonData;
    const techOk   = !hasTechFilter   || techChecked.has(c.aca_technical);
    const commitOk = !hasCommitFilter || commitChecked.has(c.aca_commitment);
    const nameOk   = !searchTerm      || c.name.toLowerCase().includes(searchTerm);
    if (techOk && commitOk && nameOk) {{
      toAdd.push(m);
      visible++;
    }}
  }});

  cluster.addLayers(toAdd);
  document.getElementById('badge').textContent = visible;
  document.getElementById('status-bar').textContent =
    `${{visible}} of ${{markers.length}} canyons`;
}}

// ── Wire events ───────────────────────────────────────────────────────────
document.querySelectorAll('.filter-cb').forEach(cb =>
  cb.addEventListener('change', applyFilters)
);
document.getElementById('search-box').addEventListener('input', applyFilters);
document.getElementById('reset-btn').addEventListener('click', () => {{
  document.querySelectorAll('.filter-cb').forEach(cb => cb.checked = true);
  document.getElementById('search-box').value = '';
  applyFilters();
}});

// Initial render
applyFilters();
</script>
</body>
</html>
"""

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Map written:  {out_path}  ({len(canyons)} markers)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run scrape.py first.")
        return

    canyons = load_canyons(CSV_PATH)
    print(f"Loaded {len(canyons)} mappable canyons from {CSV_PATH}")

    if not canyons:
        print("No mappable rows (check exclude flags and lat/lon columns).")
        return

    write_map(canyons, MAP_PATH)
    write_gpx(canyons, GPX_PATH)


if __name__ == "__main__":
    main()
