# Frame data

The **Frame Data** tab (`frame-data.html`) reads `games.json`, then one JSON file per game in the `frame-data/1` format below.
The page knows nothing about where the numbers came from, so every source only has to write the same format.

## Files

- `games.json` — the games the tab offers: `id`, `name`, `data` (the game's JSON), `icons` (folder with `icons.json`) and optionally `models` (folder with `models.json`, for the 3D preview).
- `elden-ring.json` — Elden Ring, patch 1.17.3. Built by `tools/frame_data/import_er_game.py` straight from an installed
  copy of the game (see below). `tools/frame_data/import_er_nyasu.py` builds the same file from the
  [Elden Ring Frame Data Explorer](https://er-frame-data.nyasu.business) by Emilia (sovietspaceship) instead.
- `models/elden-ring/` and `viewer3d.js` — the 3D preview in each move's sheet (see [3D preview](#3d-preview)).
- `icons/elden-ring/` — 96px WebP inventory icons per weapon and `icons.json` (weapon name → file, source page). Built by
  `tools/frame_data/import_er_icons.py` from the [Elden Ring Wiki](https://eldenring.wiki.gg), with the
  [Elden Ring Fan API](https://eldenring.fanapis.com) as fallback.

Rebuild (downloads are cached in `.cache/`, which git ignores):

```bash
python tools/frame_data/import_er_game.py "D:/SteamLibrary/steamapps/common/ELDEN RING"   # your install folder
python tools/frame_data/import_er_nyasu.py        # or from the explorer: ... 1.14.1 for another patch
python tools/frame_data/import_er_icons.py
```

### Reading the game files

`import_er_game.py` only reads the install; nothing there is changed or unpacked to disk. It needs Windows (the game's
own Oodle DLL decompresses the archives), Python 3.14+ and the `cryptography` package, and downloads two kinds of
community reference data once: param layouts from [Paramdex](https://github.com/soulsmods/Paramdex) and the archive
header keys from [UXM Selective Unpack](https://github.com/Nordgaren/UXM-Selective-Unpack). File formats are in
`tools/frame_data/er_files.py`.

- `regulation.bin` (AES, then ZSTD): EquipParamWeapon gives each weapon's class, moveset sections and behavior variation;
  BehaviorParam_PC and AtkParam_Pc give stamina, motion value, damage level and physical type of the first hit.
- `c0000.anibnd` in the Data archives: one TAE per moveset section. Event 1 (304 for criticals) is a hitbox, event 300 a
  cancel window for the regular equip load (else jump table event 0), jump table 5 the get-parried window, 791/795 hyper
  armor, and 608 a playback speed change that shifts every later frame.
- `item_dlc02.msgbnd`: English weapon names.

Against the explorer's 1.17 data, startup, cancels, totals and armor agree on 96–98% of moves and the weapon lists on all
of them. Not read yet: poise damage, damage of skill-buffed heavies (War Cry, Barbaric Roar) and i-frames beyond
the jump table's dodge flag.

## 3D preview

A move's detail sheet shows the move played on the game's own models when `games.json` gives the game a `models`
folder and that folder's `models.json` lists the move: play/pause, frame stepping (`,` `.` or the arrow buttons),
scrubbing on the frame strip, slow motion, and the move's hitboxes drawn on exactly the frames the table calls active.
`frame-data/viewer3d.js` does this with three.js (loaded from jsDelivr through the page's import map).

```bash
python tools/frame_data/export_er_models.py "D:/SteamLibrary/steamapps/common/ELDEN RING"   # ~1 minute
```

writes `models/elden-ring/` from the install (read-only, same archive readers as above):

- `armor-raging-wolf.glb`: the Raging Wolf set skinned to the c0000 skeleton (`chr/c0000.anibnd` → `Skeleton.hkx`),
  rest pose = the Havok reference pose, meshes the set's own `invisibleFlag`s hide left out, low-res (`_l`) albedo
  textures only. Game space is left-handed, so the viewer mirrors X once at the root.
- `weapon-<name>.glb`: weapon models (`parts/wp_a_XXXX`), origin at the grip; the viewer attaches them to `R_Weapon`.
  Each class previews its icon weapon (`EXPORT` in the script, Katana → Moonveil); moves that weapon doesn't use play
  with the first weapon that does.
- `anim/<move id>.json`: the move's animation (`chr/c0000_aXx.anibnd`, spline-compressed Havok 2018, decoded by
  `tools/frame_data/er_havok.py`): per-frame local rotations (int16 quaternions, base64) for the animated bones,
  translations where they move, root motion, and `time`, the animation time of each real frame after TAE speed changes.
- `models.json`: per move (`<class>|<id>`) its weapon, frame count and hits: TAE hitbox events (event 1 / 304) with
  real-frame `start`/`end`, resolved through BehaviorParam_PC → AtkParam_Pc to shapes (`a`, `b` dummy poly ids, `r`
  radius; a capsule when `b` is set). Dummy points are listed per weapon (weapon model space) and for the body (`body`:
  bone, offset in that bone's space). Ids from 10000 up name their source (10xxx right weapon).

Not covered yet: other classes and armor sets (change `EXPORT`), hitboxes of skill-buffed heavies (War Cry, Barbaric
Roar fire projectiles, BulletParam isn't read), weapon-specific animations (sheaths, Moonveil's scabbard), cloth
physics, and the left hand.

These files are FromSoftware's assets, converted from a retail install. Hosting them publicly is a legal exposure the
site owner accepts; they are kept small (low-res textures, one set, a few weapons) and can be removed by deleting
`models/` and the `models` entry in `games.json`.

## Format `frame-data/1`

```jsonc
{
  "schema": "frame-data/1",
  "game":   {"id", "name", "fps", "version", "frameNote"},
  "source": {"name", "url", "author", "retrieved", "method", "note", "moveUrl", "moveName", "links"},
            // moveUrl: optional link per move, "{id}" = move id, labelled moveName (else name);
            // links: optional [{name, url}] — when present the footer shows note plus these links
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
