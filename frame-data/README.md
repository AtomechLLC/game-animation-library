# Frame data

The **Frame Data** tab (`frame-data.html`) reads `games.json`, then one JSON file per game in the `frame-data/1` format below.
The page knows nothing about where the numbers came from, so every source only has to write the same format.

## Files

- `games.json` — the games the tab offers: `id`, `name`, `data` (the game's JSON), `icons` (folder with `icons.json`) optionally `models` (folder with `models.json`, for the 3D preview) or `clips` (folder of per-move hitbox clips).
- `stores.json` — where each game is sold, plus your Steam Curator and affiliate ids. See [Store links](#store-links).
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
- `hollow-knight.json` — Hollow Knight (Steam build), frames of 1/60 s. Built by `tools/frame_data/import_hk_game.py`
  from an installed copy (see [Hollow Knight](#hollow-knight)), which also writes `sprites/hollow-knight/` for the
  2D preview and `icons/hollow-knight/`.
- `devil-may-cry-3.json` — Devil May Cry 3: Special Edition (PS2, Europe), 60 fps, Dante's 118 weapon and style moves.
  Built by `tools/frame_data/import_dmc3_game.py` from the disc's files (see [Devil May Cry 3](#devil-may-cry-3)),
  which also writes `icons/devil-may-cry-3/`; `tools/frame_data/export_dmc3_models.py` writes `models/devil-may-cry-3/`
  for the 3D preview.
- `ninja-gaiden-black.json` — Ninja Gaiden Black (Xbox), 60 fps, Ryu's Dragon Sword. Built by
  `tools/frame_data/import_ngb_game.py` from the game disc (see [Ninja Gaiden Black](#ninja-gaiden-black)), which also
  writes `sprites/ninja-gaiden-black/` for the 2D preview and `icons/ninja-gaiden-black/`.
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

## Hollow Knight

```bash
python tools/frame_data/import_hk_game.py "Z:/SteamLibrary/steamapps/common/Hollow Knight"   # ~3 minutes, sprites included
python tools/frame_data/import_hk_game.py <install> --no-sprites                               # frame data only
python tools/frame_data/import_hk_game.py <install> knight.nail.slash                          # re-render these moves
```

Reads only (UnityPy, TypeTreeGeneratorAPI, Pillow). The Steam build is Unity 6 with Mono scripts and no type trees,
so `hk_unity.py` lays MonoBehaviours out from the game's own `Managed/*.dll` (TypeTreeGeneratorAPI misses the align
after `m_Enabled`, and nested string lists need its own reader) and decodes PlayMaker FSM actions from their
`ActionData` (`paramDataType`, `byteData` and the typed lists). `hk_tk2d.py` cuts 2D Toolkit sprites out of their
atlases; `hk_fsm.py` walks FSMs to time them; `hk_render.py` draws a move's timeline into sheets.

Everything comes from the Knight prefab in `resources.assets` (the GameObject with `HeroController`):

- Nail slashes: `NailSlash.FixedUpdate` turns a slash's `PolygonCollider2D` on at physics step 1 and off at step 5,
  so the hitbox is out from 20 to 80 ms (frames 2–5). Physics runs at 50 Hz (`TimeManager`). Dash, jump and cast are
  allowed after `ATTACK_RECOVERY_TIME`, the next slash after `ATTACK_COOLDOWN_TIME`.
- Nail arts (Nail Arts FSM) are timed from the release. Great Slash and Dash Slash count physics steps in their own
  Control Collider FSM; Cyclone Slash's hits are out while it spins (0.45 s without extra presses).
- Spells (Spell Control FSM): each spell's states give the Knight's clips and when the hit objects switch on; the hit
  objects' Hit Box Control FSMs switch their colliders on and off at their clip's trigger frames. Vengeful Spirit's
  projectile flies at the spawner FSM's speed. Dives are shown cast from the ground.
- Movement: dash times, i-frames (shadow dash, quake landing, taking a hit), jump steps and gravity
  (Physics2D gravity −60 × `DEFAULT_GRAVITY`), focus (Focus Start Time + 33 Soul × Time Per MP Drain).
- Damage is base damage: nail 5 (Old Nail) to 21 (Pure Nail), nail arts as a multiple of it, spells from each hit
  object's Set Damage FSM.

The 2D preview's sheets are drawn from the same timelines: the Knight's tk2d clips, the slash and spell effect
objects with their own clips and transforms, attack polygons (red) and the `HeroBox` hurtbox (blue), mirrored to face
right. Polygons are stored as `[kind, [x, y, ...]]` and sprites.json sets `smooth` for the painted art.

Bosses (Hornet twice, Mantis Lord, Soul Master, Pure Vessel, Nightmare King Grimm) come from their Godhome arena
scenes (`level<n>`, numbered as in the build's scene list). An attack walks the boss's main FSM from an antic state
until it reaches a state where the boss chooses again (Idle, Escalation, a choice, the next antic); `BOSSES` in the
importer lists the attacks and times the few events the walk can't (a dash ending at a wall, the needle coming
back). Attack hitboxes are the boss's DamageHero children while the FSM has them switched on (ActivateGameObject or
SetPolygonCollider); the hurtbox is the body collider, resized per state by SetBoxCollider2DSizeVector, and the
per-pose collider children that carry ExtraDamageableProxy. Damage is in masks.

Not read yet: wall jump, Crystal Heart, charm variants (only noted in More), boss projectiles and spawned hazards
(boomerangs, orbs, firebats, spikes: those attacks show their length only), other enemies.

Silksong's Hornet is a character of the same game (family Silksong), added with `--silksong <Silksong install>`:

```bash
python tools/frame_data/import_hk_game.py "Z:/SteamLibrary/steamapps/common/Hollow Knight" --silksong "Z:/SteamLibrary/steamapps/common/Hollow Knight Silksong"
```

Silksong ships its assets as Addressables bundles; `hk_unity.Game` reads them, takes MonoScripts from the
monoscripts bundle and finds the bundle behind a `CAB-…` reference through an index cached in
`.cache/hollow-knight-silksong/`. The hero prefab (Hero_Hornet) is in `heroloading_assets_all.bundle`
(`hk_silksong.py`). Silksong's NailSlash switches a slash's collider on at its effect clip's first trigger frame and
off at the second, so Hunter crest slash windows come from the clips. The crest configs (attack duration, cooldown,
down spike and dash stab times) are referenced from a bundle that is not shipped, so Silksong moves have no cancel
frames and only the Hunter crest is read.

Silksong bosses (`SILKSONG_BOSSES`: Lace, Bell Beast, Last Judge, Phantom, Widow, Moss Mother) are walked the same
way as Hollow Knight's from their scene bundles (`scenes_scenes_scenes/<scene>.bundle`). Children that are always on
(contact and arena hazards) and arena-wide trigger zones are left out of the attack hitboxes; damage is the first
switched-on hitbox's DamageHero damage in masks.

Sheets are cropped only for projectiles flying far ahead, so big spell and boss effects stay whole.

`add_hk.py` renders library clips from the same sheets (hitboxes drawn on, dark background) for the moves it maps.

## Devil May Cry 3

`tools/frame_data/import_dmc3_game.py` reads Devil May Cry 3: Special Edition straight from the PS2 disc's files
(European release, SLES-54186): the folder with `GData.afs`, or a folder it was unpacked to. Read-only; the formats
are written up in `tools/frame_data/dmc3_files.py`.

```bash
python tools/frame_data/import_dmc3_game.py "D:/Games/Devil May Cry 3 SE"        # writes devil-may-cry-3.json
python tools/frame_data/export_dmc3_models.py "D:/Games/Devil May Cry 3 SE"      # writes models/devil-may-cry-3/
```

- **Which moves.** The executable (`SLES_541.86`) starts each of Dante's actions from one dispatch chain, one function
  per action id; each function plays one or more of his motion scripts by (group, index). `tools/frame_data/dmc3_moves.py`
  lists those per move, with names from the action ids (the enum in the community
  [Crimson](https://github.com/berthrage/Devil-May-Cry-3-Crimson) mod for the PC port matches the PS2 ids). Classes are the
  five devil arms, five guns and Royalguard; Swordmaster and Gunslinger moves sit under their weapon with type
  Swordmaster / Gunslinger.
- **Total.** A script plays one motion of a motion pack (`pl000_00_<n>.pac`) from a start frame to its last frame; the
  spans of a move's scripts added up are its total. A combo part's motion carries the parts before it and the script
  starts it where the previous part handed over, so totals count from there.
- **Cancels.** A script also sets per-input next-action policies as the motion plays (buffer, act, off). The first frame
  it lets an input act is the cancel: `attack` (melee), `dodge` (jump or roll), `block` (Royalguard), `skill` (style
  move) and `move` (plain movement, the end of recovery). They come from the move's last script.
- **Icons.** Each weapon's icon is its HUD icon, and Royalguard's is its style emblem, from `id100.pac` (the HUD
  archive; texture slots 42-50 and 30-38 for the weapons, 24 for Royalguard, as the Crimson mod's `HUD.cpp` reads
  them), cropped and centred at 96 px.
- **Not known yet.** When the hit comes out isn't in the scripts or any data file; the executable decides it, so startup,
  active frames, recovery and the 3D preview's hitboxes are left out for now. Also not listed yet: the guns' normal
  aimed shots and Twosome Time (their motions come from aim tables), Trickster, Quicksilver and Doppelganger moves
  (started outside the action dispatch), and damage.

## Ninja Gaiden Black

```bash
python tools/frame_data/import_ngb_game.py "C:/Games/Ninja Gaiden Black.iso"     # or a folder holding cmn.afs and chr_ryu.afs
python tools/frame_data/import_ngb_game.py <iso> --no-sprites                    # frame data only
```

Reads only (numpy, Pillow). The disc is an Xbox XDVDFS image read by `ngb_xiso.py`; game data is in CRI AFS archives.
Formats are in `tools/frame_data/ngb_files.py`, worked out from the bytes and the game's code (disassembled with the
[ngbrecomp](https://github.com/gamboozino/ngbrecomp) toolkit); notes in `scouting-ninja-gaiden-black.md`.

- `cmn.afs/ryu.mtn`, section 1: one timeline script per player state. `0 <frame>` waits for that frame of the state's
  motion. `0x0d slot state` switches an attack on (1) and off (0 or 4): slot 0 is the sword, 0x0c and up the feet,
  so startup and active windows read straight out of it. `9 1` / `9 0` open and close the combo input window
  (player+0x27ac = 2), which the input rules test before chaining to the next attack: that is the tab's → Attack.
- `cmn.afs/rm_kt.mot`: the Dragon Sword's motions (a script's motion 10000 + n). Total is the motion's length.
  Recovery is total minus the last active frame; no dodge-cancel marker has been decoded yet.
- Names and inputs: `ryu.chr` holds the input rules as a small bytecode (interpreter at xbe 0x16300: state and
  state-group tests, button tests per weapon, then the state to go to), which gives the chains (X → XX → XXX,
  XX → XXY → XXYY → XXYYY, XX → XX6X → XX6XX / XX6XY, XY launcher → air XXX → X or Y, ...). The names are the
  game's own technique list in `default.xbe`. Moves the chains don't reach with certainty are left out.
- The Ultimate Technique family (Haze Straight Slash, its Essence and Ultimate versions) shares one animation and
  timing; only the effects differ.

The 2D preview is not the game's model: `sprites/ninja-gaiden-black/` draws a figure posed from the game's animation
(root, spine and head rotations, limbs as two-bone IK chains to the motion's end-effectors) seen from the side, the
sword along the right hand's rotation, and the sword (or foot) attack capsule in red on the active frames. Sword
length and placement are approximate. `add_ngb.py` renders library clips from the same sheets.

Not read yet: other weapons (the scripts and rules are there: nunchaku, Warhammer, ...), damage, Izuna Drop's throw
after the grab, flying-swallow and wall moves, the model's meshes.

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

### Devil May Cry 3

```bash
python tools/frame_data/export_dmc3_models.py "<folder with GData.afs>"   # ~1 minute
```

writes `models/devil-may-cry-3/` in the same layout (about 2.4 MB):

- `dante.glb`: Dante's body (`pl000.pac` slot 1) on his 24-bone skeleton with the textures of slot 0, scaled from
  centimetres to metres. His coat (slot 12) is cloth-simulated in the game; here each coat vertex takes the skin of the
  nearest hip or leg vertex, eased toward the lower body further down, so it swings with the legs.
- `weapon-<name>.glb`: each weapon's MOD (`plwp_*.pac` slot 1), origin at the grip, on the right hand (and node `L`
  on the left hand for Ebony & Ivory and Agni & Rudra).
- `anim/<move>.bin`: the move's motions played in a row from each script's start frame, sampled at 60 fps (`FDA2`);
  root motion carries on from one motion to the next.
- `moves/<class>.json`: per move its `anim`, `frames` and preview `weapon`; `hits` is empty until hit windows are found.

These are Capcom's assets, under the same terms as the Elden Ring files above.

## Store links

The game header shows where to buy the game, from `frame-data/stores.json`. Edit that file to add ids; the page needs
no code changes, and an empty value just hides that link.

- `games.<id>.steam`: the Steam app id. Street Fighter III: 3rd Strike is only on Steam inside the Street Fighter 30th
  Anniversary Collection, so it links that (`via` names what the button buys). `games.<id>.eshop` is a Nintendo eShop
  URL, used for Smash Ultimate, which is Switch only.
- `steam.curatorId`: your Steam Curator group id (the number in `store.steampowered.com/curator/<id>-Name/`). Steam
  links then carry `?curator_clanid=<id>`, which credits your curator page in Steam's referral stats. **Steam pays
  nothing for this**: it has no public affiliate program. Create a curator page at
  https://store.steampowered.com/curators/ (a Steam account is enough).
- `affiliates.<store>.link`: your affiliate link template for a store that sells Steam keys and pays commission
  (Humble Store, Fanatical, Green Man Gaming). The store's button appears on every Steam game once this is set.
  `{url}` is replaced with the store's page for the game, `{enc}` with the same URL percent-encoded, for networks that
  take the destination as a parameter. Copy the deep-link format from the program's dashboard, for example:
  - a store's own partner id: `{url}?partner=YOUR_ID` (`?` becomes `&` when the page already has a query string)
  - an affiliate network deep link: `https://network.example/c/123/456/789?u={enc}`

  Sign up at https://promo.humblebundle.com/affiliates, https://www.fanatical.com/en/affiliates and
  https://www.greenmangaming.com/affiliates/ (GMG runs its program on Impact). The store page defaults to the store's
  search for the game; set `games.<id>.pages.<store>` to a product URL to link the exact page instead. Affiliate
  buttons get `rel="sponsored"` and the footer adds a disclosure line.

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
