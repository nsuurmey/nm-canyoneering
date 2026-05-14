# Doug Scott Slot Canyon Map

Interactive trip-planning map built from [Doug Scott's slot canyon catalog](https://www.dougscottart.com/hobbies/canyons/canyons.htm).

Three-step pipeline: **scrape → review CSV → render**.

---

## Prerequisites

```bash
pip install -r requirements.txt
```

Tested with Python 3.10+.

---

## Step 1 — Scrape

```bash
python scrape.py
```

Fetches every canyon subpage from dougscottart.com (≈ 80–120 canyons expected).
Saves raw HTML to `data/raw/` so you can reparse without re-fetching.

**Outputs:**
- `data/canyons.csv` — full canyon catalog
- `parse_errors.log` — rows where GPS parsing failed

Runtime: ~2 min (1 s crawl delay between requests).

---

## Step 2 — Manual CSV review ⚠️

**This step is not automated.** Open `data/canyons.csv` in a spreadsheet editor.

1. Cross-reference `parse_errors.log` — these canyons have no coordinates yet.
2. For high-priority canyons, look up coords via Google Maps / CalTopo and paste them into `lat` / `lon`.
3. Set `coord_source = manual` for any you fill in by hand.
4. Set `exclude = true` for canyons you want in the CSV but off the map.

CSV schema:
```
name, url, lat, lon, aca_rating, aca_technical, aca_water, aca_commitment,
region, coord_raw, coord_source, notes, exclude
```

---

## Step 3 — Render

```bash
python render.py
```

Reads `data/canyons.csv`, skips `exclude=true` and empty `lat`/`lon` rows.

**Outputs:**
- `output/map.html` — open in any browser; no server needed
- `output/canyons.gpx` — import into GAIA GPS (File → Import)

---

## Map features

- **Tile layer:** OpenTopoMap (topo detail, no API key required)
- **Clustering:** markers cluster by default, expand on zoom
- **Popups:** canyon name, ACA rating, region, link to Doug's page
- **Filter sidebar:** filter by technical rating, commitment rating, or name search
- **Reset:** one click to clear all filters

---

## Updating canyon data

The pipeline is designed for one-time scrape + manual maintenance.
To add or correct a canyon, edit `data/canyons.csv` directly and re-run `render.py`.

---

## Data source

GPS coordinates, ACA ratings, and descriptions scraped from  
[dougscottart.com](https://www.dougscottart.com/hobbies/canyons/canyons.htm)  
© Doug Scott. For personal trip-planning use only.
