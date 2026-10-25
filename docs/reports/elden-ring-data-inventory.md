# Elden Ring data inventory

Where the repository's Elden Ring data lives, what each piece means, and which of it matters for the planned
Elden Ring viewport and inspector.

- **Snapshot:** branch `ux/elden-ring-viewport-inspector` at commit `031d53d` (2026-10-24). Game data is patch
  1.17.3, regulation 11730034, read from the game files on 2026-10-22.
- **Scope:** Elden Ring only. Covers the data, its provenance and its current presentation. It does not propose a
  design; section 7 lists open questions for that work.
- **Judged against:** the intended experience in [`CLAUDE.md`](../../CLAUDE.md): find relevant examples, observe
  deliberately, compare approaches, use examples in teaching, and contribute confidently.

## 1. Summary

Elden Ring data sits in five places that barely reference each other:

1. **The atlas**, in `library.json` and `gifs/`, presents moves as examples of an action such as "sprint attack" or
   "knockdown".
2. **The Frame Data tab**, in `frame-data/elden-ring.json`, shows per-move timing and damage in a sortable table and
   a details sheet.
3. **The 3D preview data**, in `frame-data/models/elden-ring/`, holds skeleton, weapon and armor models, baked
   animation, and hitbox shapes.
4. **The render tooling**, in `tools/er_gifs/`, turns 3D preview animations into the atlas's Elden Ring clips.
5. **The curation records**, in `gif-screening.json` and `missing-references.json`, track clip quality and gaps.

A student who wants to study one move (watch it frame by frame, see when the hitbox is out, compare it with a
similar move, then find which atlas entry it illustrates) has to visit at least two pages. Several of the connections
needed for that journey do not exist (section 6).

The data most worth bringing together in one view is the **animation, hitbox shapes and phase timeline** (what
students observe) plus **move identity and the atlas entry it illustrates** (how they find and compare). Several
fields that look important are empty or mislabelled today (section 5.4).

## 2. At a glance

| Location | What it holds | Size / count | Shown in |
|---|---|---|---|
| `library.json` | Atlas entries; Elden Ring appears in example games, references and clips | 330 entries; Elden Ring mentioned by 64 | Atlas (`index.html` from `template.html`) |
| `gifs/*-er<n>.webp` | Renders of the 3D preview, 360 px, 15 fps | 35 files used by 37 clip objects on 36 entries | Atlas entry clips |
| `gifs/<id>-<n>.webp` (Tenor/Giphy) | Downloaded Elden Ring clips from GIF sites | 21 local files, 7 more link-only | Atlas entry clips |
| `frame-data/elden-ring.json` | Move table: identity, timing, cancels, armor, first-hit damage | 40 classes, 455 weapons, 3,865 moves (1.55 MB) | Frame Data tab |
| `frame-data/icons/elden-ring/` | Weapon icons (96 px WebP) and `icons.json` | 479 icons | Frame Data index, table and rail |
| `frame-data/models/elden-ring/models.json` | Skeleton, body dummy points, weapon list, class to model map | 150 bones, 218 dummies, 455 weapons, 41 classes | Used by the 3D preview |
| `frame-data/models/elden-ring/moves/*.json` | Per-class hit windows and hitbox shapes | 41 files (40 classes + `common`) | 3D preview hitboxes |
| `frame-data/models/elden-ring/anim/*.bin` | Baked animation (`FDA2` format) with root motion | 3,990 files (3,745 moves + 245 Common), 79 MB | 3D preview, renders |
| `frame-data/models/elden-ring/*.glb` | Raging Wolf armor and 450 weapon models | ~57 MB | 3D preview, renders |
| `tools/er_gifs/jobs.json` | Which animation renders into which atlas entry | 35 jobs | Not shown; build input |
| `tools/er_gifs/common_anims.json` | Labelled catalogue of non-weapon animations | 245 ids in 30 `want` groups | Not shown; build input |
| `gif-screening.json` | Results of a frame-by-frame clip check | 41 Elden Ring `added`, 2 in `review` | Feeds `screened` notes on clips |
| `missing-references.json` | Entries without web references | 14 mention Elden Ring | Not shown |
| `gif-blocklist.json`, `marks.json` | Removed clips; clips marked bad during local review | Both empty | Admin / local review |
| `tools/frame_data/*er*` | Extractors and file-format readers | 9 scripts | — |

## 3. Data dictionary

Frame numbers are TAE animation frames at **30 fps, counted from 1**. Startup is the first frame the hitbox is out
(`game.frameNote` in `elden-ring.json`).

Where the columns say "Shown in":

- **Table** is a Frame Data column.
- **Sheet** is the move details sheet (`openMove`, `frame-data.html:427-447`).
- **Dock** is the 3D preview (`dock`/`preview`, `frame-data.html:462-487`; `frame-data/viewer3d.js`).
- **Rail** is the filter sidebar.

### 3.1 Move identity (`elden-ring.json` → `moves[]`)

| Field | Meaning | Origin | Shown in |
|---|---|---|---|
| `id` | Animation id `aSSS_NNNNNN` (TAE section + animation). Not unique: 118 ids appear in two classes, so the page keys rows by `class\|id` | TAE | Sheet only ("Animation {id}") |
| `class` | Weapon class (Katana, Greatsword, …), one of 40 | `EquipParamWeapon.wepType` | Table, rail, index |
| `type` | Move type, one of 14 in play order: light, heavy, feint, running, rolling, backstep, crouch, jumping, guard-counter, critical, parry, shieldpoke, buffed, mounted | Keyword match on `name` (`er_common.move_type`) | Rail filter, group rows |
| `grip` | 1h, 2h, Paired (powerstance), Offhand, Mounted, any | Name prefix (`er_common.grip`) | Table (1H/2H/PS/OH/Horse), rail |
| `name` | Human label, e.g. "1h R1 1" | `MOVE_NAMES` table copying Frame Data Explorer naming | Table, dock header |
| `weapons` | Indexes into the class's weapon list for weapons that use this animation | Weapon moveset sections | Sheet ("Used by"); drives listing when a weapon is picked |
| `default` | Part of the class's standard moveset (2,568 moves) | Most-used TAE section per class | Not shown; decides what lists with no weapon picked |

### 3.2 Timing (`elden-ring.json` → `moves[]`)

| Field | Meaning in design terms | Origin | Shown in |
|---|---|---|---|
| `startup` | Anticipation: frames until the first hitbox | First `active` frame | Table (coloured fast ≤12, slow ≥30), dock header |
| `active` | Hitbox windows `[[start,end]]`, inclusive | TAE event 1 (304 for criticals/throws) | Strip; sheet lists ranges |
| `activeFrames` | Total frames a hitbox is out | Sum of `active` | Table |
| `hits` | Number of hitbox windows | `len(active)` | Table tag "×N", rail "Multi-hit" |
| `recovery` | Frames from the last active frame until dodge is possible: the commitment after the hit | `cancels.dodge − 1 − last active` | Table, strip, sheet |
| `total` | **Labelled "animation length", but computed as the frame where the last cancel window ends** (see 5.4) | Max cancel-window end | Table, sheet |
| `cancels.attack` / `.dodge` | First frame the next attack / a dodge can interrupt | TAE event 300 or jump-table event 0 | Table (→ Attack, → Dodge), strip |
| `cancels.block` / `.skill` / `.item` / `.move` | First frame guard, weapon skill, item use, walking can interrupt | Same | Sheet only |
| `armor` | Hyper-armor windows: the move is not staggered by hits | TAE events 791/795 | Table tag "HA", strip band, dock HUD, rail |
| `iframes` | Invulnerability windows | Jump table 8 | Strip band, sheet, dock HUD; **empty on all moves** |
| `parryable` | Can be parried | Jump table 5 present | Table tag "NP" when false, sheet, rail |

### 3.3 First-hit damage (`elden-ring.json` → `moves[].damage`)

| Field | Meaning | Origin | Shown in |
|---|---|---|---|
| `type` | Physical damage type: Slash, Strike, Pierce, Standard | `AtkParam_Pc.atkAttribute` | Table |
| `mv` | Motion value (100 = base weapon damage) | `AtkParam_Pc.atkPhysCorrection` | Table |
| `level` | Damage level: how hard the hit staggers the target | `AtkParam_Pc.dmgLevel` | Sheet only |
| `stamina` | Stamina cost of the move | `BehaviorParam_PC.stamina` | Sheet only |
| `poise` | Poise damage | Not read by the game importer | Table column and sheet; **always "—"** |

### 3.4 3D preview data (`frame-data/models/elden-ring/`)

| Data | Meaning | Used by |
|---|---|---|
| `models.json` `skeleton` | 150 bones; `R_Weapon` / `L_Weapon` attach points; `Master` root | Viewer |
| `models.json` `body` | 218 body dummy points `id → [bone, x, y, z]`; anchors for body hitboxes (kicks, shield bashes) | Viewer (only those hitboxes reference) |
| `models.json` `weapons` | 455 `{id, model, file, variation}`; `variation` picks the weapon's hitbox set | Viewer |
| `models.json` `classes` | Class → move file, preview weapon, `hand: "L"` for bows | Viewer |
| `models.json` `armor` | Haligtree Knight Set, the one armor the character wears | Viewer ("Haligtree Knight Set · {weapon}") |
| `weapon-wp_a_XXXX.glb` | Weapon mesh; root `extras.dummies` hold blade points hitboxes attach to | Viewer |
| `moves/<class>.json` `moves[id]` | `frames` (clip length), `weapon`, `hits[{start, end, judge, hand?}]` | Viewer: hitbox timing in 3D |
| `moves/<class>.json` `attacks` | Per weapon `variation` → `judge` → shapes `{a, b, r, type}`: sphere at dummy `a`, or capsule `a`–`b`, radius `r` | Viewer draws spheres/capsules; `type` unused |
| `anim/<id>.bin` | `FDA2`: per-frame bone rotations and translations plus root motion (`export_er_models.py:419-442`) | Viewer and renders |
| `moves/common.json` | 245 non-attack animations (walks, rolls, hit reactions, gestures, ladders, doors) with no hits | GIF renders only; not in the Frame Data tab |

The viewer (`frame-data/viewer3d.js`) plays, pauses, steps ±1 frame (`,` / `.`), scrubs, and runs at 1×, ½×, ¼× or
0.1×. It can toggle hitboxes, show ghost hitboxes on every frame, and toggle root motion. It does **not** draw
hurtboxes (none exist in the data), and it does not draw cancel, armor or i-frame windows in 3D. Those appear only on
the scrub strip and in the HUD text (`frameState`, `frame-data.html:455-458`).

### 3.5 Atlas (`library.json` → `animations[]`)

| Field | Meaning | Elden Ring relevance |
|---|---|---|
| `id`, `name`, `category`, `subcategory`, `tags`, `description` | The action being taught, e.g. `melee.sprint-attack` | No description or tag names Elden Ring |
| `example_games` | Games that show the action; feed the atlas game filter and "Seen in" chips | 34 entries list Elden Ring (29 plain, 5 with a suffix such as "Spirit Ash") |
| `references[]` | `{title, url, source, game, note}` web references | 36 Elden Ring references on 19 entries |
| `gifs[]` | Clips: `page_url`, `media_url`, `title`, `game`, `host`, `local` (plays inline only if set), `source_url`, `screened` | 65 Elden Ring clips on 52 entries: 37 renders, 25 Tenor, 3 Giphy |
| `gifs[].screened` | `{verdict, confidence, what}` from the clip check | 43 Elden Ring clips carry one |
| `rejected_gifs[]` | Removed clips, kept for the record; not shown | 1 Elden Ring-tagged (a Dark Souls meme) |

### 3.6 Render jobs (`tools/er_gifs/`)

| Field | Meaning |
|---|---|
| `jobs[].out` | Output file `gifs/<out>.webp`; the entry id is `out` without `-er<n>` |
| `jobs[].class`, `move` / `moves` | Source animation(s); 31 jobs use `Common`, 4 use weapon classes (Katana, Greatsword, Greatshield) |
| `jobs[].label`, `what` | Clip title and screening description |
| `jobs[].confidence` | `low` on 7 weaker matches (deathblow, ladder climb, posture break, pushback on block, kick door, pick up, photo pose) |
| `jobs[].weapon`, `grip`, `bare` | Weapon override, left-hand hold, or no weapon |
| `jobs[].also` | Other entries that reuse the same render (2 jobs) |
| `common_anims[]` `{id, label, want}` | Human label and purpose for each Common animation, grouped by `want` (roll 15, death 15, door/lever 15, jump 14, fall 14, knockdown 14, guard 14, gesture 13, …) |

## 4. Provenance and reproducibility

| Data | Source | Needs a local game install? |
|---|---|---|
| Timing, cancels, armor, parry, damage, weapon lists | Game files via `tools/frame_data/import_er_game.py` (`regulation.bin` params, TAE events) | Yes, on Windows (uses the game's Oodle DLL) |
| Move names, "Open in Frame Data Explorer" link | Frame Data Explorer by Emilia (`MOVE_NAMES`, `source.moveUrl`) | No |
| Param layouts, archive keys | Paramdex, UXM (formats only) | No |
| Icons | eldenring.wiki.gg via `import_er_icons.py` (reads the Nyasu cache for the weapon list) | No |
| Models, animation, hitbox shapes | `export_er_models.py` (~15 min), `export_er_common.py` | Yes |
| Renders | `tools/er_gifs/render.js` (Playwright + ffmpeg) over the 3D preview | No (uses committed assets) |
| Atlas clips and references | Web search on Tenor/Giphy and wikis, then screening | No |

Notes:

- `import_er_nyasu.py` can rebuild `elden-ring.json` from the Explorer instead. It writes the same file, so whichever
  importer runs last wins; nothing is merged. The Explorer version would carry `damage.poise`. The README reports the
  two sources agree on 96–98% of moves.
- 3D assets are FromSoftware's, converted from a retail install (noted in `frame-data/README.md`).

## 5. What matters, judged against CLAUDE.md

### 5.1 Core for observing (the viewport itself)

| Data | Why it matters |
|---|---|
| Baked animation with root motion (`anim/*.bin`, skeleton, armor, weapon models) | *Observe deliberately*: the thing students inspect frame by frame. It already supports stepping and slow motion. |
| Hitbox shapes and windows (`moves/<class>.json` `hits` + `attacks`) | Shows where and when the attack can connect: the spatial side of "game feel" that tables cannot convey. |
| Phase timeline: `startup`, `active`, `recovery`, `cancels.dodge`, `cancels.attack`, `armor` | Gives the frames meaning: anticipation, contact and commitment. Students need it beside the animation, not on another page. |

### 5.2 Core for finding and comparing

| Data | Why it matters |
|---|---|
| Move identity: `class`, weapon (`weapons`), `type`, `grip`, `name` | *Find relevant examples* and *compare approaches*: the axes for picking "the same kind of move" across weapons. |
| The atlas entry a move illustrates (now only implied by `tools/er_gifs/jobs.json`) | Links a move to the action vocabulary of the library, which also spans other games. |
| Elden Ring renders (`gifs/*-er<n>.webp`) | The atlas's best Elden Ring material: clean, consistent, and screened. They replace weak placeholder GIFs, as the project intended. |
| Common animations (`common_anims.json` labels + `anim/`) | Most atlas Elden Ring entries are locomotion, reactions, defense and interaction, not weapon attacks. These 245 animations are their source but are invisible in the Frame Data tab. |

### 5.3 Supporting context (the inspector's secondary layer)

- `damage.mv`, `damage.type`, `damage.level`, `damage.stamina`: useful for explaining *why* a move is tuned the way it
  is, but they apply to the first hit only.
- `parryable`, `cancels.block` / `.skill` / `.item` / `.move`.
- Weapon icons: fast visual recognition when browsing.
- Atlas references and "Open in Frame Data Explorer": routes to deeper study and teaching material.
- `screened` notes and `confidence: low`: tell an instructor how much to trust a clip, and invite contribution.

### 5.4 Low value now, or unreliable

| Data | Issue |
|---|---|
| `iframes` | Empty on all 3,865 moves, yet the UI reserves space for it (strip band, sheet, HUD). |
| `damage.poise` | Never present; the default **Poise** column always shows "—". |
| `total` | README and column tooltip call it the animation length. It is the end of the last cancel window and matches the clip length (`frames`) on only 13 of 3,511 comparable moves. |
| `damage` | Empty on 476 moves (all buffed moves); 13 more have only `stamina`. |
| Jumping moves | 352 have no `recovery`, `total` or `cancels`. |
| Move type `parry` | Listed in `moveTypes`, but no moves have it. |
| Shape `type`, `body` dummies, `weapons[].model` | Exported but never shown; low value to learners. |
| Hitboxes of skills (judge ≥ 1000) | 1,273 of 6,609 hits have no shape, so the preview says "hitbox shape not in data". |
| Two moves | `a050_035040` (Reaper) and `a062_030040` (Beast Claw) have no animation. |

## 6. Disconnects

These gaps are why the same move cannot be studied in one place today.

1. **Only 4 of 37 renders link to Frame Data.** They are the weapon-class renders (`melee.sprint-attack`,
   `melee.rolling-attack`, `melee.shield-bash`, `melee.deathblow`). Their link is
   `frame-data.html#c=<class>&t=<type>&m=<move>`, but `fromHash` (`frame-data.html:495-500`) ignores `m`, so it opens
   a filtered table, not the move. It also omits `w=`, although the title names the weapon.
2. **The 33 Common renders have no Frame Data counterpart.** `Common` is not a class in `elden-ring.json`, and the
   source animation ids are recorded only in `tools/er_gifs/jobs.json`, not in `library.json`. Their "↗" link opens
   the WebP file.
3. **Frame Data never links back to the atlas.** A Greatsword running heavy appears in both places with no
   connection.
4. **The atlas game filter misses most renders.** 28 of the 36 entries with an Elden Ring render do not list Elden
   Ring in `example_games`, and the filter reads only that field (`template.html:299-301`).
5. **Timing is split across three surfaces.** The table shows some cancels, the sheet shows all cancels plus damage
   level and stamina, and the dock shows hitboxes and the strip but not the numbers. The 3D hit windows (move files)
   and `active` (table) cover the same frames on every move except two ground-stab backstabs (Backhand Blade
   `a265_031730`, Great Katana `a061_031730`), whose move files have no hits. The move files list windows in a
   different order, and once per hand.
6. **The move id is nearly hidden.** It appears only in the sheet's footer, although it is the key joining every
   dataset (`elden-ring.json`, `moves/*.json`, `anim/*.bin`, `jobs.json`, Frame Data Explorer).
7. **Curation records are stale in places.**
   - `gif-screening.json` lists `melee.overhead-slam-1.webp` and `melee.dual-wield-flurry-0.webp` under both
     `removed` and `added`, because the file names were reused.
   - `needs_replacement` still lists `expression.point-beckon`, which now has a high-confidence render.
   - `missing-references.json` still lists `expression.point-beckon` and `reactions.burning`, which have
     references.
   - Clip `game` strings vary ("Elden Ring: Shadow of the Erdtree" vs "Elden Ring Shadow of the Erdtree").
   - `magic.summon-0` is titled Elden Ring but screened as a Dark Souls clip.

## 7. Open questions for the viewport and inspector

These are assumptions to test, not decisions.

- **The unit of study.** Is it a *move* (Frame Data's unit) or an *atlas entry* (an action that may have several
  moves and other games)? The answer decides what the inspector is anchored to.
- **The join key.** Assumption: a shared key of `class` + move `id` is enough to join timing, hitboxes, animation,
  renders and atlas entries. That needs `jobs.json`'s move ids carried into the library, and `m=` honoured in
  links.
- **Common animations.** Should they become browsable (with `common_anims.json` labels) so locomotion, reactions and
  interactions can be observed like attacks?
- **Timeline in the viewport.** Should the phase timeline (startup, active, recovery, cancels, armor) sit directly
  under the viewport, with the numbers in the inspector, so observation and numbers stay in sync?
- **Fields to hide until they are reliable.** Should `iframes`, `poise` and the mislabelled `total` be hidden or
  relabelled so learners are not misled?
- **Teaching use.** What must a shareable link capture (move, frame, speed, hitbox toggle) so an instructor can point
  students to an exact moment?

## Appendix: how the counts were obtained

All counts are from read-only Python queries on the committed files at `031d53d`:

- `elden-ring.json`: `len(moves)`, the sum of `len(classes[].weapons)`, moves with non-empty `iframes`, moves with
  `damage.poise`, empty `damage`, jumping moves with `total is None`.
- `total` vs clip length: compared `moves[].total` with `moves/<class>.json` → `moves[id].frames`, keyed by
  `(class, id)`, over the moves with a non-null `total` that have a move file entry (3,511).
- Files: glob counts of `frame-data/icons/elden-ring/*.webp`, `frame-data/models/elden-ring/anim/*.bin`,
  `weapon-*.glb`, `gifs/*-er[0-9]*.webp`.
- `library.json`: clips with `host == "Elden Ring render"`, of which those whose `page_url` contains
  `frame-data.html`; entries whose `example_games`, `references[].game` or `gifs[].game` contain "elden".
- Hit windows: compared the set of `(start, end)` pairs in `moves[].active` with those in the move files' `hits`.
- `fromHash` behaviour: read directly in `frame-data.html:495-500`.

Other figures (hit and shape totals, `screened` counts, `want` groups, curation-file records) come from a survey of
the same files and the extractor source.
