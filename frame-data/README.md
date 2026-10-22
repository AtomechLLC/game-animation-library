# Frame data

The **Frame Data** tab (`frame-data.html`) reads `games.json`, then one JSON file per game in the `frame-data/1` format below.
The page knows nothing about where the numbers came from, so a new source (for example reading the game files directly)
only has to write the same format.

## Files

- `games.json` — the games the tab offers: `id`, `name`, `data` (the game's JSON) and `icons` (folder with `index.json`).
- `elden-ring.json` — Elden Ring, patch 1.17. Built by `tools/frame_data/import_er_nyasu.py` from the
  [Elden Ring Frame Data Explorer](https://er-frame-data.nyasu.business) by Emilia (sovietspaceship).
- `icons/elden-ring/` — 96px WebP inventory icons per weapon and `index.json` (weapon name → file, source page). Built by
  `tools/frame_data/import_er_icons.py` from the [Elden Ring Wiki](https://eldenring.wiki.gg), with the
  [Elden Ring Fan API](https://eldenring.fanapis.com) as fallback.

Rebuild (downloads are cached in `.cache/`, which git ignores):

```bash
python tools/frame_data/import_er_nyasu.py        # or: ... 1.14.1 for another patch
python tools/frame_data/import_er_icons.py
```

## Format `frame-data/1`

```jsonc
{
  "schema": "frame-data/1",
  "game":   {"id", "name", "fps", "version", "frameNote"},
  "source": {"name", "url", "author", "retrieved", "method", "note", "moveUrl"},  // moveUrl: link per move, "{id}" = move id
  "families":  [{"id", "name"}],                                  // groups of classes (ruler + index sections)
  "classes":   [{"id", "name", "family", "icon", "weapons": [names], "moves"}],  // icon: weapon name shown for the class
  "moveTypes": [{"id", "name", "description"}],                   // in play order; class view groups by these
  "grips":     [{"id", "name"}],
  "moves": [{
    "id", "class", "type", "grip", "name",
    "startup",            // first active frame (1-based)
    "active": [[s, e]],   // hitbox windows, 1-based inclusive
    "activeFrames", "hits",
    "recovery",           // frames from the last active frame until a dodge is possible (null if unknown)
    "total",              // animation length in frames (null if unknown)
    "cancels": {"attack", "dodge", "block", "skill", "item", "move"},   // first frame each is possible; keys optional
    "armor":   [[s, e]],  // hyper armor windows
    "iframes": [[s, e]],
    "parryable",
    "damage": {"type", "mv", "poise", "level", "stamina"},             // first hit; keys optional
    "weapons": [i],       // indexes into the class's weapons that use this animation
    "default"             // part of the class's default moveset (shown when no weapon is picked)
  }]
}
```

Picking a weapon shows the moves whose `weapons` include it; with no weapon picked, a class shows its `default` moves.
Any field a source can't provide can be `null` or left out, and the page shows "—".
