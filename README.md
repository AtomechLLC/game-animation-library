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

## Clip screening

`gif-screening.json` records a frame-by-frame check of every downloaded clip for memes, reaction edits, TV/anime/real-life footage and clips that don't show the named move. Clips flagged at medium or high confidence were deleted from `gifs/` and moved to the animation's `rejected_gifs` list (with a `screened` note) so the page no longer shows them. Low-confidence or unclear calls stay in `gifs` with a `screened` note for a human to check. `needs_replacement` lists animations left with no screened local clip.
