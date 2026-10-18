# Game Combat Animation Library

A catalogue of 330 video game animations across 20 categories (combat and non-combat), each with a description, tags, example games, web references and GIF examples. `template.html` renders it as a browsable page (the "atlas").

## Rebuilding

```bash
python build_index.py taxonomy.txt index.json
python merge.py
```

`merge.py` writes `library.json`, `atlas.html` and `todo.json`. `index.json`, `atlas.html` and `todo.json` are generated, so they are ignored by git.

## GitHub Pages

On every push to `main`, `.github/workflows/static.yml` runs `python3 build_page.py index.html` (template.html + library.json) and publishes the repo root, so the site always matches the committed `library.json`. Run `python build_page.py` locally to preview `index.html`.

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

## Clip screening

`gif-screening.json` records a frame-by-frame check of every downloaded clip for memes, reaction edits, TV/anime/real-life footage and clips that don't show the named move. Clips flagged at medium or high confidence were deleted from `gifs/` and moved to the animation's `rejected_gifs` list (with a `screened` note) so the page no longer shows them. Low-confidence or unclear calls stay in `gifs` with a `screened` note for a human to check. `needs_replacement` lists animations left with no screened local clip.

## Community features (xCloud / any PHP host)

`index.php` serves the atlas with voting (▲/▼ on every GIF), "Suggest a replacement" / "Suggest a GIF" (link or file upload),
and an owner review page (`admin.php`). GIFs that collect enough downvotes are flagged and queued for a Giphy/Tenor
replacement search (`tools/find_replacements.php`); candidates wait for review like community suggestions.
Setup: [DEPLOY-XCLOUD.md](DEPLOY-XCLOUD.md). Code: `api.php`, `admin.php`, `lib/bootstrap.php`, `config.sample.php`.

## Local review: mark bad GIFs with ✕

On Windows, double-click `serve_local.bat` (or run `python serve_local.py`). Your browser opens http://localhost:8765; keep the console window open while you review.

- Open an entry and press **✕ Bad GIF** under any clip you want replaced, or **✕ Needs better GIFs** for the whole entry. Press again to unmark.
- Cards with marks show a red ✕; the **Only entries marked bad ✕** filter lists them.
- Marks are saved instantly to `marks.json` in this folder (entry id and name, GIF key, page URL, local file, title, time).

To get replacements, ask Claude to "search for better GIFs for my marks". Claude reads `marks.json` from this folder on your computer or from the repo (commit and push it), finds candidates for each marked entry, and clears the marks it has handled.
