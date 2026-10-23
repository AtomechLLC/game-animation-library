# Game Animation Library

A catalogue of 330 video game animations across 20 categories (combat and non-combat), each with a description, tags, example games, web references and GIF examples. `template.html` renders it as a browsable page (the "atlas").

## Rebuilding

```bash
python build_index.py taxonomy.txt index.json
python merge.py
```

`merge.py` writes `library.json`, `atlas.html` and `todo.json`. `index.json`, `atlas.html` and `todo.json` are generated, so they are ignored by git.

## GitHub Pages

On every push to `main`, `.github/workflows/static.yml` runs `python3 build_page.py index.html` (template.html + library.json) and publishes the repo root, so the site always matches the committed `library.json`. Run `python build_page.py` locally to preview `index.html`.

## Frame Data tab

`frame-data.html` is a second tab with per-move frame data (startup, active, recovery, cancels, hyper armor, damage), starting
with Elden Ring: browse by weapon class and weapon (icon index), then by move type, or sort and filter every class at once.
It is a static page that loads `frame-data/games.json` and one JSON file per game, so it works on GitHub Pages, `server.js`
(`/frame-data`) and `serve_local.py` alike. Data format, sources and rebuild steps: [frame-data/README.md](frame-data/README.md).

## Source data

- `taxonomy.txt` — the hand-written index. One `# CAT id | Name | description` line per category, then one line per animation: `Name | Subcategory | tags,comma,separated | Game;Game;Game | Description`.
- `build_index.py taxonomy.txt index.json` — turns the taxonomy into JSON (ids are `category.slug`).
- `library.json` — the full library: categories plus animations with `references` (title, url, source, game, note) gathered by web search.
- `merge.py` — run in a folder holding `index.json`, `refs*.json` and `template.html`; merges reference files and writes `library.json`, `atlas.html` and `todo.json` (animations still missing references).
- `gifs` field on each animation — GIF examples found on Tenor/Giphy: `page_url` (always), `media_url` (direct file, only when the search page exposed it), `title`, `game`, `host`. Picked from Tenor descriptions, not watched; spot-check before relying on one. Files saved at `gifs/<id>-<n>.gif|webp|mp4` get a `local` path and play inline on the page.
- `missing-references.json` — animations still without web references.
- `template.html` — the library page; `__DATA__` is replaced with library.json.

To add animations: append lines to taxonomy.txt, rebuild index.json, rerun merge.py, republish the page.

- `gifs/` — downloaded copies (Tenor's 200px animated WebP, Giphy's 200w WebP), one per GIF that could be fetched. `local` is the path, `source_url` the file it came from. Tenor links whose page id is 18-20 digits map straight to a media URL; older 7-8 digit ids could not be resolved, so those links stay page-only.
- `add_ufd.py` — adds Super Smash Bros. Ultimate hitbox GIFs from [Ultimate Frame Data](https://ultimateframedata.com) to 29 melee, fighting, defense and reaction entries, saved as 400px WebP at `gifs/<id>-ufd-<n>.webp` (host `Ultimate Frame Data`). The move-to-entry mapping is in the script; rerunning skips GIFs already present.

## Street Fighter III: 3rd Strike (Baston)

[Baston](http://ensabahnur.free.fr/BastonNew/) by ensabahnur is a 3rd Strike frame data site with hitboxes and a
sprite capture of every frame, extracted from the CPS3 emulator FBA-RR. Two scripts bring it in:

- `python tools/frame_data/import_baston_sf3.py` writes `frame-data/street-fighter-3-third-strike.json` (all 20
  characters, 1,303 moves) and the animated stance icons in `frame-data/icons/street-fighter-3-third-strike/`, for the
  Frame Data tab. Downloads are cached in `.cache/baston/`.
- `python tools/frame_data/export_baston_sprites.py` (after the importer) packs every move's frame captures and boxes into
  `frame-data/sprites/street-fighter-3-third-strike/` (~50 MB) for the hitbox preview docked above the 3rd Strike move
  table (`frame-data/sprites2d.js`, in place of the 3D preview).
- `python add_baston.py` (after the importer) renders mapped moves from those frame captures, with Baston's hurtboxes
  and attack boxes drawn on, to `gifs/<id>-baston-<n>.webp` (60 fps, host `Baston`) and adds them to `library.json`
  and to `added` in `gif-screening.json`. The move-to-entry mapping is `MAP` in the script.

Sprites are Capcom's; every clip and move links back to its Baston hitbox viewer.

## Elden Ring renders

`tools/er_gifs/` renders Elden Ring animations with the Frame Data tab's 3D preview to animated WebP for library
entries. `jobs.json` maps an entry to a class and move id (or several ids played in a row); `node tools/er_gifs/render.js`
(Playwright + ffmpeg) loads `render.html`, which runs `frame-data/viewer3d.js` paused, seeks it frame by frame, reads each
frame off the canvas, crops to the character over the whole job and writes `gifs/<entry>-er<n>.webp` (360 px, 15 fps).
Then `python tools/er_gifs/add_to_library.py` adds each render to its entry (and any `also` entries) with host
`Elden Ring render`, and to `added` in `gif-screening.json`.

Weapon moves come from the weapon classes. Rolls, backsteps, locomotion, hit reactions, guard, deaths, object actions and
gestures come from the `Common` class: `python tools/frame_data/export_er_common.py "<install>"` bakes the ids listed in
`tools/er_gifs/common_anims.json` (each with a label and what it was wanted for) into the same `anim/` folder.
`render.js --sheet DIR [id or want ...]` draws 8-frame contact sheets of those ids, which is how the ids in `jobs.json`
were picked. Clips the game shows against props (ladder, door, item) are rendered without the prop.
## Removed GIFs (blocklist)

`gif-blocklist.json` lists GIFs removed for good on the review page: their `page_url`, `media_url`, `source_url` and the
SHA-256 of the file. Refresh it from the site with **Export blocklist** on /admin (or
`python blocklist.py --from https://YOUR-SITE/api?action=blocklist`), then run `python blocklist.py`: it moves every
matching GIF in `library.json` to `rejected_gifs` (verdict `blocklisted`) and deletes its file from `gifs/`.
Any pass that adds GIFs must skip candidates on the list: `from blocklist import load, blocked` and drop a candidate
when `blocked(load(), gif, file_bytes)` is true. The site reads `gif-blocklist.json` too.

## Clip screening

`gif-screening.json` records a frame-by-frame check of every downloaded clip for memes, reaction edits, TV/anime/real-life footage and clips that don't show the named move. Clips flagged at medium or high confidence were deleted from `gifs/` and moved to the animation's `rejected_gifs` list (with a `screened` note) so the page no longer shows them. Low-confidence or unclear calls stay in `gifs` with a `screened` note for a human to check. `needs_replacement` lists animations left with no screened local clip.

Clips added later to fill empty or single-clip entries are listed under `added` in `gif-screening.json` and carry a `screened` note with verdict `added`; confidence `low` marks a weaker match worth a second look.

## Community features (xCloud / any Node.js host)

`server.js` (Node.js 20+, no dependencies) serves the atlas with voting (▲/▼ on every GIF), "Suggest a replacement" /
"Suggest a GIF" (link or file upload, including short videos that are converted to a GIF with ffmpeg,
which the app downloads if needed), and an owner
review page at `/admin`. Submitted GIFs (uploads and links) are
stored on the site and stay hidden until approved; an approved replacement takes the original GIF's place on the page.
GIFs that collect enough downvotes are flagged and queued for a Giphy/Tenor replacement search; candidates wait for
review like community suggestions.
Setup: [DEPLOY-XCLOUD.md](DEPLOY-XCLOUD.md). Code: `server.js`, `lib/*.js`, `.env.example`.

## Local review: mark bad GIFs with ✕

On Windows, double-click `serve_local.bat` (or run `python serve_local.py`). Your browser opens http://localhost:8765; keep the console window open while you review.

- Open an entry and press **✕ Bad GIF** under any clip you want replaced, or **✕ Needs better GIFs** for the whole entry. Press again to unmark.
- Cards with marks show a red ✕; the **Only entries marked bad ✕** filter lists them.
- Marks are saved instantly to `marks.json` in this folder (entry id and name, GIF key, page URL, local file, title, time).

To get replacements, ask Claude to "search for better GIFs for my marks". Claude reads `marks.json` from this folder on your computer or from the repo (commit and push it), finds candidates for each marked entry, and clears the marks it has handled.
Replacement clips are saved as `gifs/<id>-r<n>.webp` (Tenor 200px WebP); the clips they replace move to `rejected_gifs` with a `screened` note and are listed under `removed` in `gif-screening.json`.
