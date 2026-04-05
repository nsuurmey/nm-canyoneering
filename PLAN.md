# Plan: Deploy NM Canyoneering App to GitHub Pages

## Overview

Deploy the static New Mexico Canyoneering web app (currently packaged as a zip file) to GitHub Pages at `nsuurmey.github.io/nm-canyoneering`.

The app is a purely static site (HTML + CSS + JS + JSON) with no build step. All external dependencies (MapLibre GL, Google Fonts, OpenFreeMap tiles) are loaded from CDNs.

---

## Steps

### 1. Extract the zip and clean up the repo

- Unzip `New Mexico Canyoneering.zip` into the repo root, producing:
  - `index.html`
  - `style.css`
  - `app.js`
  - `canyons_data.json`
- Delete `New Mexico Canyoneering.zip` from the repo (no longer needed).

### 2. Clean up `index.html`

- Remove the injected Perplexity inline-edit script block (`<script data-pplx-inline-edit>` through its closing `</script>`, lines 169-229 in the original file). This was added by the preview tool and is not part of the app.

### 3. Set up GitHub Pages deployment via GitHub Actions

Since the repo doesn't use a framework or build tool, use a simple static deployment workflow.

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Pages
        uses: actions/configure-pages@v5
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: "."
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### 4. Enable GitHub Pages in repository settings

- Go to **Settings > Pages**
- Set **Source** to **GitHub Actions**

(Or the implementing agent can use the GitHub API to configure this.)

### 5. Verify deployment

- After pushing to `main`, confirm the GitHub Actions workflow runs successfully.
- Visit `https://nsuurmey.github.io/nm-canyoneering/` and verify:
  - The map loads and shows canyon markers
  - The table view renders with all 129 canyons
  - Filters, search, sorting, and theme toggle work
  - The site is responsive on mobile viewports

---

## Adding New Canyon Data in the Future

The canyon data lives in `canyons_data.json` as a flat JSON array. To add new canyons:

1. Open `canyons_data.json`
2. Add a new object to the array following this schema:

```json
{
  "name": "Canyon Name",
  "url": "https://ropewiki.com/Canyon_Name",
  "class": "2A III",
  "lat": 35.1234,
  "lon": -106.5678,
  "distance_mi": 42,
  "rappels": "3",
  "longest_rappel_ft": "80",
  "quality": 3.5,
  "season": "Mar, Apr, Oct, Nov",
  "notes": "Short approach"
}
```

Field notes:
- `lat`/`lon`: Use `null` if unknown (the canyon will appear in the table but not on the map)
- `distance_mi`: Straight-line distance from Albuquerque in miles; use `null` if unknown
- `rappels`: Use `"—"` (em dash) if none
- `longest_rappel_ft`: Use `"—"` (em dash) if not applicable
- `quality`: 0-5 scale; use `0` for unrated

3. Commit and push to `main` — the site will auto-deploy via GitHub Actions.

---

## File Structure After Completion

```
nm-canyoneering/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── index.html
├── style.css
├── app.js
├── canyons_data.json
└── PLAN.md          (this file — can be deleted after work is done)
```
