# Frame data

The **Frame Data** tab (`frame-data.html`) reads `games.json`, then one JSON file per game in the `frame-data/1` format below.
The page knows nothing about where the numbers came from, so every source only has to write the same format.

## Files

- `games.json` — the games the tab offers: `id`, `name`, `data` (the game's JSON), `icons` (folder with `icons.json`) optionally `models` (folder with `models.json`, for the 3D preview) or `clips` (folder of per-move hitbox clips).
- `elden-ring.json` — Elden Ring, patch 1.17.3. Built by `tools/frame_data/import_er_game.py` straight from an installed
  copy of the game (see below). `tools/frame_data/import_er_nyasu.py` builds the same file from the
  [Elden Ring Frame Data Explorer](https://er-frame-data.nyasu.business) by Emilia (sovietspaceship) instead.
- `no-rest-for-the-wicked.json` — No Rest for the Wicked (Steam build 22928553), 60 fps. Built by
  `tools/frame_data/import_nrftw_game.py` from an installed copy (see [No Rest for the Wicked](#no-rest-for-the-wicked)),
  which also writes `icons/no-rest-for-the-wicked/`.
- `street-fighter-3-third-strike.json` — Street Fighter III: 3rd Strike, 60 fps, all 20 characters. Built by
  `tools/frame_data/import_baston_sf3.py` from [Baston](http://ensabahnur.free.fr/BastonNew/) (see
  [Street Fighter III: 3rd Strike](#street-fighter-iii-3rd-strike)), which also writes `icons/street-fighter-3-third-strike/`.
- `sprites/street-fighter-3-third-strike/` and `sprites2d.js` — the 2D hitbox preview docked for 3rd Strike (see
  [2D preview](#2d-preview)).
- `super-smash-bros-ultimate.json` — Super Smash Bros. Ultimate, 60 fps, all 89 characters. Built by
  `tools/frame_data/import_ufd_ssbu.py` from [Ultimate Frame Data](https://ultimateframedata.com/smash) (see
  [Super Smash Bros. Ultimate](#super-smash-bros-ultimate)), which also writes `icons/super-smash-bros-ultimate/` and
  the hitbox clips in `clips/super-smash-bros-ultimate/`.
- `clipviewer.js` — the hitbox clip preview docked above the move table for games with `clips` (see [Hitbox clips](#hitbox-clips)).
- `models/elden-ring/` and `viewer3d.js` — the 3D preview docked above the move table (see [3D preview](#3d-preview)).
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

## No Rest for the Wicked

```bash
python tools/frame_data/import_nrftw_game.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked"   # ~1 minute
```

Reads only (UnityPy and lz4). The gameplay simulation is Photon Quantum, so every combat number lives in
`StreamingAssets/quantumDatabase.bin` (LZ4 MessagePack with field names, decoded by `nrftw_files.py` and cached in
`.cache/nrftw/`), and enum names come from the unencrypted IL2CPP metadata (`nrftw_il2cpp.py`). Asset paths and English
names come from the `qdb_assets` Addressables bundle.

- `worldlut.asset` lists every weapon with its class filter, moveset (`.actions`) and collider data. A class filter's
  `.actions` is the class default; a weapon's own `.actions` replaces whole slots. Slots are `ArmamentActionType`:
  runes, normal combos, run, quickstep, roll, knockdown (get-up), plunge and parry, each a list in combo order. Each
  weapon builds its own combo from shared animations, so a move row is one action at one combo step
  (`<class>.<type><step>.<action>`), and `weapons` lists who uses it there.
- Combo steps are usually windup actions holding a tap version (`light`) and a hold version (`charged`, with `charge`
  = frames held, from the windup's `AllowChargeAttack` section).
- Per action, `TimelineData`: `WeaponColliders` windows are the hitboxes (projectile and spawned-entity times for
  bows, wands and runes, the parry window for parries); `Sections` give cancels (`InterruptibleByAll`,
  `InterruptibleByMovement`, `InterruptibleByNextAttack`, and `InterruptibleByAction` with an `ActionType` mask:
  dodge, block, melee, special), `Invincibility` i-frames and `Immunity*` armor windows; `Duration` the total.
  `DamageConfig` gives the damage school and whether it can be parried. The action's `Segments` (designer
  startup/active/recovery) agree with the hitbox startup on 89% of moves; the rest have hitboxes later than the
  segment says, and the hitboxes win.

Not read yet: damage numbers (they scale with the weapon's stats), stamina (weight-based), the `PowerArmour` level
some attacks carry, and the per-weapon damage overrides in each `.actions` slot.

## Street Fighter III: 3rd Strike

```bash
python tools/frame_data/import_baston_sf3.py      # ~1,300 pages from a hobby site, fetched slowly and cached in .cache/baston/
```

Baston (by ensabahnur, data from the CPS3 emulator FBA-RR; hitbox work by LennethEX, Dammit, C_cube and
ComedyBlissOption) has per character a table per move group (normals, specials, Super Arts, Yun's Genei-Jin moves,
movement) and per move a hitbox page with every frame's boxes. Classes are characters (no weapons), move types are
those groups and grips are stances (standing, crouching, air).

- Startup is the table's startup + 1 (Baston counts the frames before the hit). Active windows come from the hitbox
  pages: a frame is active when the character or a projectile has an attack box, or the character a throw box.
  Superfreeze frames are dropped, so Super Arts are timed from the end of the freeze. A projectile's box shows a frame
  before the table counts it, so windows start no earlier than the startup; where the capture's first box comes much
  later (Denjin Hadouken fully charged) the capture wins. Hitbox startup and the table agree on 92% of moves.
- Total is the hitbox page's length (it agrees with startup + active + recovery on 707 of 760 moves where all three
  are known); recovery is total minus the last active frame.
- Advantage on block, hit and crouching hit, damage, stun, guard (H/L), cancels (SA, SP, SC, NC, DC, SJ), kara and
  throw range and super bar gain come from the tables. Movement rows have a length only.

## 2D preview

When `games.json` gives a game a `sprites` folder instead of `models`, the dock above the move table plays moves from
sprite sheets with their boxes drawn on, like [Baston](http://ensabahnur.free.fr/BastonNew/)'s hitbox viewer:
play/pause, one-frame steps (`−1 f` / `+1 f`, or `,` `.`), scrubbing on the frame strip, slow motion, and a toggle per
box kind (hurtbox, other vulnerability, attack, throw, throwable, pushbox). `frame-data/sprites2d.js` has the same
interface as `viewer3d.js` (`classData`, `createViewer` → `show`, `prefetch`, `dispose`), so the page docks either.

```bash
python tools/frame_data/export_baston_sprites.py              # after import_baston_sf3.py; ~50,000 frames, cached
python tools/frame_data/export_baston_sprites.py ken ryu.special.035   # only these characters or moves
```

writes `sprites/street-fighter-3-third-strike/` from Baston's per-frame captures (384x224, character on a key colour)
and boxes:

- `sheets/<move id>.webp`: the move's frames, keyed to transparency, cropped to the character, its projectiles and its
  boxes over the whole move, packed left to right and top to bottom in one lossless WebP. Frames are the tab's frames:
  superfreeze, the commit frame and the closing neutral frame are left out, so frame N is frame N in the table.
- `moves/<character>.json`: per move id `sheet`, cell size `w` x `h`, `cols`, and `frames`: per frame a list of boxes
  `[kind, x1, y1, x2, y2]` in cell pixels, inclusive. Kinds are `p`, `v`, `a` (projectiles included), `t`, `ta`, `pu`.
- `sprites.json`: `fps`, box kind names, `source`, and per character its moves file.

The sprites are Capcom's, the captures and boxes Baston's; the dock credits Baston under the controls.

## Super Smash Bros. Ultimate

```bash
python tools/frame_data/import_ufd_ssbu.py            # 90 pages at one a second, cached in .cache/ufd/
python tools/frame_data/import_ufd_ssbu.py --clips    # also every move's hitbox GIF (~3,200, a couple of hours)
```

Ultimate Frame Data (MetalMusicMan, Zeckemyro and contributors) has a page per character with ground attacks,
aerials, specials, grabs/throws and dodges. Classes are characters (no weapons), move types are those sections, and
grips are ground and air. Misc Info (stats, ledge options) is left out.

- Startup, total frames and endlag (the tab's recovery) are the site's; where a cell has several values (`6/15`,
  `5...`) the first is used and the cell is kept under More. Active windows come from the active frames text: every
  frame or range in it, parenthesised later hitboxes included (`6—9(10—25)` is 6–9 and 10–25).
- On shield (`blockAdv`), shield stun (`shieldStun`), landing lag (`landingLag`) and damage are kept as the site
  writes them: a number, or text when the move has several hitboxes (`-15/-16`, read with the "Values are for"
  line under More). Shield lag, autocancel hops and notes go under More.
- I-frames and armor come from the notes ("Intangible on frame 3-21", "heavy armor (4%) on frame 7-9"); partial
  intangibility (arm, head) counts too, so read the note.
- Each move's `clips` are its hitbox GIFs: `file` (under the game's clips folder), `frames`, `label` and `source`.
  A GIF frame is a game frame (Mario's jab: 19 frames, 19 total), so frame N of a clip is frame N in the table.

Footage is Nintendo's and the GIFs are Ultimate Frame Data's; every move links to its character page and each
clip to its GIF.

## Hitbox clips

For a game whose `games.json` entry has `clips` (a folder) and a character picked, `clipviewer.js` docks the move's
hitbox clip above the table instead of the 3D preview, with the same controls: play/pause, one-frame steps,
scrubbing on the frame strip and speed (¼× by default, about the site's own speed). Moves with several clips (angled
tilts and smashes, early/late) get a button per clip. Frames are decoded once with `ImageDecoder` (kept for the last
six clips); browsers without it get the WebP playing by itself.

Clips are animated WebPs fitted in 440×280 at quality 50, about 60 KB each.

## 3D preview

When a weapon class is picked and `games.json` gives the game a `models` folder whose `models.json` covers the
class's moves, a 3D preview docks above the move table (sticky under the header on wide screens). Clicking a row swaps
that move in place without reloading the models; "Frame details" opens the detail sheet. It plays the move on the
game's own models: play/pause, one-frame steps (`−1 f` / `+1 f`, or `,` `.`), scrubbing on the frame strip, slow
motion, and the move's hitboxes drawn on exactly the frames the table calls active. `frame-data/viewer3d.js` does
this with three.js (loaded from jsDelivr through the page's import map).

It holds the weapon picked above the table; with no weapon picked, each move plays with its class's preview weapon
(`EXPORT` in the exporter: the class's first weapon, Katana → Moonveil) or, when that weapon doesn't use the move, the
first weapon that does. Powerstance moves hold the weapon in both hands, off-hand attacks and bows in the left.

```bash
python tools/frame_data/export_er_models.py "D:/SteamLibrary/steamapps/common/ELDEN RING"   # ~15 minutes
python tools/frame_data/export_er_models.py "<install>" Katana "Great Katana"                # only these classes
```

writes `models/elden-ring/` for every class and weapon in `elden-ring.json` (read-only, same archive readers as above):

- `armor-raging-wolf.glb`: the Raging Wolf set skinned to the c0000 skeleton (`chr/c0000.anibnd` → `Skeleton.hkx`),
  rest pose = the Havok reference pose, meshes the set's own `invisibleFlag`s hide left out, low-res (`_l`) albedo
  textures only. Game space is left-handed, so the viewer mirrors X once at the root.
- `weapon-wp_a_XXXX.glb`: one file per weapon model (`parts/wp_a_XXXX`; a few weapons share one), origin at the grip,
  256 px textures, int16 positions and int8 normals (`KHR_mesh_quantization`). The root node's `extras.dummies` holds
  the model's dummy points (weapon model space). The viewer attaches it to `R_Weapon` and/or `L_Weapon`.
- `anim/<move id>.bin`: the move's animation baked to one pose per tab frame (30 fps real time, after TAE speed
  changes), so frame N in the preview is frame N in the table. Motion comes from `chr/c0000_aXx.anibnd`, or
  `c0000_dlc01` / `c0000_dlc02` for DLC movesets (spline-compressed Havok 2018, decoded by
  `tools/frame_data/er_havok.py`); animations that borrow another's motion (TAE header ImportsHKX) are followed. Per
  bone: 32-bit smallest-three quaternions and int16 millimetre translations, per frame or once when constant; then
  root motion. Byte layout at `bake()` in the exporter.
- `models.json`: skeleton bone names, the armor, every weapon (`model`, `file`, behavior `variation`), body dummy
  points (`body`: bone, offset in that bone's space), and per class its preview `weapon`, `hand` (`L` for bows) and
  moves `file`.
- `moves/<class>.json`: per move id its `frames`, preview `weapon` and `hits`: TAE hitbox events (event 1 / 304) with
  tab-frame `start`/`end`, the behavior `judge` and, for powerstance, the `hand` that swings. `attacks` resolves
  variation → judge through BehaviorParam_PC → AtkParam_Pc to shapes (`a`, `b` dummy poly ids, `r` radius; a capsule
  when `b` is set), so each weapon shows its own hitboxes. Ids from 10000 up name their source (10xxx weapon).

About 115 MB in all: ~60 MB of animation for 3,700 moves, ~50 MB of weapon models, 3.5 MB of armor.

Not covered yet: other armor sets (change `EXPORT`), hitboxes of skill-buffed heavies (War Cry, Barbaric Roar fire
projectiles, BulletParam isn't read), weapon-specific animation (sheaths, Moonveil's scabbard, whip and flail
chains) and cloth physics.

These files are FromSoftware's assets, converted from a retail install. Hosting them publicly is a legal exposure the
site owner accepts; they are kept small (low-res textures, one armor set) and can be removed by deleting `models/` and
the `models` entry in `games.json`.

### No Rest for the Wicked

```bash
python tools/frame_data/export_nrftw_models.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked"   # ~2 minutes
```

writes `models/no-rest-for-the-wicked/` in the same layout, read-only, with UnityPy (`nrftw_unity.py` reads prefabs,
meshes, textures and Mecanim clips; no AssetRipper or FBX step):

- `armor-knight.glb`: the Knight set (male), its four part prefabs skinned to the `playerRig.fbx` skeleton. The armor
  meshes' bone lists are stripped in the prefabs, so joints come from each mesh's bone name hashes (CRC32 of the bone
  path). 512 px albedo, each texture stored once. Unity space, mirrored at the root like Elden Ring.
- `weapon-<name>.glb`: each weapon's view prefab, node `R` (and `L` for dual weapons) at the grip, attached to
  `armR1_hand_weapon_socket` / `armL1_hand_weapon_socket`. 256 px textures, int16 positions.
- `anim/<action>.bin`: the action's clips (qanim → SourceAnim → AnimationClip; streamed Hermite, dense and constant
  curves) at 60 fps, `FDA2` with the header's spare byte = 2: bone poses every second frame, which the viewer
  interpolates; root motion (root_JNT's translation) every frame. Only the 114 bones the armor skins are kept.
- `moves/<class>.json`: per move its `anim`, `frames`, preview `weapon` and `hits` (window and collider id), and
  `boxes` per weapon: its ColliderData box per collider id (`e` half extents, `o` centre, `r` rotation, `hand` L for
  left-hand colliders), drawn on the hand socket. A box runs from its Offset along the socket's +Y for twice its Y
  extent: that lands on each weapon's own mesh (Claymore blade, scythe head, spear shaft).
- Timing: the game retimes clips (segment `RetimingFrames`, an Animations FrameCount shorter than the clip). Each
  action's baked WeaponColliders curves record the hand socket's path per game frame (root_JNT space, rotation
  included), so the exporter time-warps the clip to follow that path and uses the result when it stays within 8 cm
  while the hitbox is out (about half the moves); otherwise the clip plays at its own speed. On those moves the baked
  path doesn't follow the visual clip at any timing, which is why boxes are anchored to the socket, not to the path.

About 33 MB in all: 18 MB of animation for 558 actions (1,339 moves), 13 MB of weapon models (162; Gutterpig and
Reibach's Claws have no mesh yet), 1.2 MB of armor and the move files. Not covered yet: other armor sets (`EXPORT`), runes' projectiles and spawned areas
(their active frames show, no shape), and cloth.

`tools/frame_data/export_nrftw_common.py "<install>"` then adds the "Common" class (`moves/common.json`, 80 clips,
1.6 MB): quicksteps, rolls, sneaking, swimming, mantles, ladder, wall and rope climbing, listed in
`tools/er_gifs/nrftw_common_anims.json`. They aren't Quantum actions but ClipAnimations of the hero's
`playerMoonAnimatorDefinition`, found by weapon group (`oneHandedAnimationSet`...) or blend space; ids are
`<context>-<name>`.

These are Moon Studios' assets, under the same terms as the Elden Ring files above.

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

Optional, for fighting games (3rd Strike and Ultimate use them): `labels` (wording: `class`, `classes`, `allClasses`, `allFamilies`,
`grip`, `everyClass`, `patch`, `pickClass`, `classView`, `recovery`, `search`), `columns` (which table columns show,
by key: `input`, `blockAdv`, `hitAdv`, `dmg`, `stun`, `guard`, `cancel`, `landing`, `sstun` beside the defaults),
`columnNames` (`{key: name}` or `{key: [name, tooltip]}` to rename a column), and per move `input`,
`blockAdv` / `hitAdv` / `crHitAdv` (a number, or text such as `KD` or a range), `damage.amount` / `stun` / `guard`,
`cancelTo` (list of cancel tags), `landingLag`, `shieldStun`, `clips` (see [Hitbox clips](#hitbox-clips)), `extra` ({label: value} shown under More) and `url` (its own source link, which
wins over `moveUrl`). A class with an empty `weapons` list shows all its moves without a weapon picker, and a move
with an empty `active` list (movement) draws its length only. `icons.json` may give `lead`, the footer's wording.

Picking a weapon shows the moves whose `weapons` include it; with no weapon picked, a class shows its `default` moves.
Any field a source can't provide can be `null` or left out, and the page shows "—".
