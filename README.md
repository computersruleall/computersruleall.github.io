# computersruleall.github.io

Personal Japan travel blog — interactive Leaflet map with photo pins and GPX journey playback, plus a few standalone pages.

**Live site:** https://computersruleall.github.io/

---

## Adding a new photo (map pin)

Two files change: the photo goes in the repo root, and one line goes in `index.html`.

### 1. Upload the photo

Drop the JPG or PNG into the repo root (same folder as `index.html`). Use a plain name — no spaces, no commas — for example `kamakura_beach.jpg`.

You can do this from GitHub's web UI:

- Open the repo → click **Add file** → **Upload files**
- Drag the photo in, commit to `main` (or a branch)

You don't need to resize it. Originals of any size work — the workflow makes the small versions.

### 2. Add a marker entry to `index.html`

Find the `markersData` array (roughly line 660). Add a new object like the existing ones:

```js
{
  lat: 35.316,
  lng: 139.550,
  text: "Kamakura Beach",
  category: "photos",
  image: "kamakura_beach.jpg"
},
```

- `lat` / `lng` — from Google Maps: right-click a spot and the coordinates copy to your clipboard.
- `text` — the caption shown in the info-box popup.
- `category` — use `"photos"` for a red pin, `"journeys"` for a blue one.
- `image` — the filename you just uploaded, exactly as it appears in the repo.

### 3. Commit

That's it. On push to `main`, a GitHub Action runs `scripts/resize_photos.py`, generates `thumb/<name>.jpg` (~300 px wide, ~15 KB) and `med/<name>.jpg` (~1200 px wide, ~200 KB), and commits them back to the branch automatically. GitHub Pages then republishes the site.

You can watch it happen at **Actions** → **Resize photos** in the GitHub UI.

### Removing a photo

Delete the source file. On the next run the workflow will notice the source is gone and remove the leftover `thumb/` and `med/` variants automatically. Also remove or comment out the corresponding `markersData` entry.

---

## Running the resize script locally

Not required — the Action handles it — but useful if you want a quick preview or you're iterating on many photos:

```bash
python3 -m pip install --user Pillow
python3 scripts/resize_photos.py
```

The script is idempotent: photos whose variants already exist (and are newer than the source) are skipped, so it's safe to run over and over.

---

## Repository layout

```
index.html          Main map page (photo pins + GPX routes)
concerts.html       Concert log
matsuya.html        Nutrition comparison table
legendary.html      Single image page
<name>.jpg / .png   Photo originals (referenced by markersData)
<name>.gpx          GPS traces for the journey playback
thumb/*.jpg         Auto-generated ~300 px variants (do NOT edit by hand)
med/*.jpg           Auto-generated ~1200 px variants (do NOT edit by hand)
scripts/resize_photos.py   The resize tool
.github/workflows/resize-photos.yml   The Action that runs the tool
```

The `thumb/` and `med/` folders are committed to the repo (rather than generated at deploy time) because GitHub Pages serves static files directly — there's no build step.

---

## Local preview

```bash
python3 -m http.server 8765
```

Open http://localhost:8765/ in a browser.
