# Scouting: No Rest for the Wicked

Can we do for No Rest for the Wicked what `import_er_game.py` and `export_er_models.py` do for Elden Ring: per-move
frame data (startup, active, recovery, cancel windows, hitboxes) and the player, armor and weapon models with attack
animations for the 3D preview? Checked on 2026-10-23 against the Steam install (build-guid
`0cf57c184d674e6ca8f8aa325752016d`), read-only.

**Verdict: yes, and the frame data is easier than Elden Ring's.** Nothing is encrypted, the gameplay data is
MessagePack with field names in it, and the attack timings are stored as named fields rather than inferred from
animation events. Rough effort for the same scope as Elden Ring: about 1.5 to 2 weeks (see [Effort](#effort)).

## What the install is

| | |
|---|---|
| Engine | Unity `6000.1.15f1` (Unity 6), IL2CPP (`GameAssembly.dll` + `global-metadata.dat` v31, magic `AF1BB1FA`, not encrypted) |
| Assets | Addressables 2.6.0, 11 `UnityFS` bundles in `StreamingAssets/aa/StandaloneWindows64` (39 GB), LZ4, no encryption |
| Gameplay sim | Photon Quantum (deterministic, fixed-point). Its asset database is `StreamingAssets/quantumDatabase.bin` (528 MB, header `MOON_QDB`) |
| Online | Photon (`PhotonServer/`). Reading files on disk touches neither the servers nor any anti-cheat |

UnityPy 1.25 (already installed) opens every bundle tried, including the 10.8 GB and 7 GB ones, in under 30 seconds
each, with type trees present, so MonoBehaviour fields read without a script dump.

## Where the combat data lives

Moon keeps two copies of each gameplay asset: a Unity MonoBehaviour in `qdb_assets_all_*.bundle` that carries the
asset path and its `AssetGuid` but almost no fields, and the real data in `quantumDatabase.bin` under the same GUID.

`quantumDatabase.bin` decodes with standard libraries: a `(type id, size)` table, then LZ4 blocks wrapped as
MessagePack ext 99 (MessagePack-CSharp's `Lz4Block`), 129 MB compressed into 963 MB of MessagePack with string keys.
It parses end to end into 30,406 assets. The one quirk is Moon's own ext types (12 to 15, baked curves and bone
tracks), whose payload has a 4-byte inner header the ext length leaves out. `tools/frame_data/nrftw_files.py` is a
prototype reader that handles this and prints any asset by path:

```bash
python tools/frame_data/nrftw_files.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked" doubleDaggerAttackA1.action
```

What is in there for a move, taking the double daggers' first light attack (`Assets/actions/playerRig/dualWield/doubleDaggers/comboA/doubleDaggerAttackA1.action`) as the example:

- **Startup / active / recovery**: `TimelineData.AttackSections` = `ActiveStartTime 0.100`, `RecoveryStartTime 0.150`
  (seconds; at 60 fps the hit is live from frame 6 to frame 9). 1,509 of the 1,615 action assets of this type have an active window.
- **Cancel and interrupt windows**: `TimelineData.Sections`, a list of `{Id, Start, End, Mask}` (here id 3 from 0.417 s
  to the end, id 6 from 0.15 to 0.30 s, id 4 with two input masks, id 10 from 0.083 s). The ids are an enum
  (`ActionSectionId` in the IL2CPP metadata); their names come from a Cpp2IL or Il2CppDumper pass over the unencrypted
  metadata.
- **Hitboxes**: each weapon has a `ColliderData` asset of oriented boxes, e.g. Ash-Soothed Daggers: `rightBlade` and
  `leftBlade`, half-extents 0.07 × 0.38 × 0.10, offset −0.12 on Y. The action's `Baked.AttackBounds` gives the swing's
  2D reach, and its `ColliderWidth` the sweep width.
- **Where the hitbox is each frame**: the matching `.qanim` (e.g. `Assets/animations/player/combat/axes/attacks/attackA.qanim`)
  is the animation baked for the simulation: `FrameCount 118` (60 fps, same length as the visual clip), root motion,
  and position and rotation tracks for the body root and the weapon sockets (bone ids 0 to 5 and 1000 to 1012). Placing
  the collider boxes on those sockets gives hitboxes per frame straight from what the game simulates.
- **Per-weapon movesets and damage**: each armament has a `.actions` asset listing its actions per input slot with
  `DamageConfig` overrides (base damage, poise, stagger, kickback, `Parryable`, `BreaksBlock`, damage school), plus a
  `.armament` asset. Also present: stamina cost, `PowerArmour`, `StaminaRecoveryFreezeTime`, root motion scale,
  `IsChargedAttack`, and global kickback (hit reaction) assets.

Player actions are grouped by weapon class (`Assets/actions/playerRig/<oneHanded|twoHanded|dualWield|ranged|...>/<class>`),
about 1,600 action assets across roughly 30 classes plus spells and techniques.

## Models and animations

- **Armor**: `Assets/models/player/armors/<set>/<set>{Male,Female}ArmorSetRig.fbx` in the `duplicateassetisolation`
  bundle (skinned meshes plus `Skeleton_GRP`), assembled per slot by prefabs in `pooled_prefabs`
  (`quantumPrefabs/hero/armors/<set>/hero{Male,Female}<Set>{BodyArmor,Gloves,Helmet,Pants}.prefab`). A test export of
  the archer set to OBJ worked.
- **Weapons**: `Assets/models/equipment/...` (489 entries) with prefabs under `armaments/root`.
- **Player animations**: `Assets/animations/player/combat/<class>/attacks/*.fbx` (1,058 entries). Clips are 60 fps and,
  although the rig has a humanoid Avatar, almost all curves are plain Transform curves (axe `attackA`: 138 position,
  138 rotation, 71 scale bindings, 7 Animator curves), so they play on the skeleton without humanoid retargeting.

The gap is tooling, not access: UnityPy reads all of this but has no skinned glTF or AnimationClip exporter. Two ways:

1. **AssetRipper or AssetStudio** (both support Unity 6 bundles) export the rig and clips to FBX, then Blender or
   FBX2glTF converts to the `.glb` files `viewer3d.js` already loads. Fastest to a first result.
2. **Our own exporter** on UnityPy: decode the streamed/dense/constant clip data and write glTF, like
   `export_er_models.py` does for FLVER and Havok. More work, but one script from the install, as with Elden Ring.

## Effort

Same scope as the Elden Ring work, one person:

| Piece | Estimate | Notes |
|---|---|---|
| Frame data importer → `frame-data/no-rest-for-the-wicked.json` | 3–4 days | Asset name ↔ GUID join (done in the prototype), walk armament → actions, turn seconds into frames, name the section ids via an IL2CPP dump, English names from the localisation tables |
| Per-frame hitboxes | 1–2 days | Decode the fixed-point tracks in Moon's ext types 13/14/15, place collider boxes on sockets |
| Armor, weapon and animation export to `.glb` | 3–5 days | AssetRipper/AssetStudio + conversion first; own exporter later if wanted |
| Wiring into `games.json` and the 3D preview | 1 day | The page and viewer are game-agnostic already |

Risks: the game is still being patched, so field layouts can move between builds (record the build-guid as Elden Ring
records the patch); a few decoded maps still show a missing key in one field (seen after `ImmunitySections`), which the
importer needs to fix; and section and damage-school ids mean nothing until the IL2CPP dump names them.

## Legal

I did not review the game's EULA text. Like most publishers' terms it very likely restricts reverse engineering and
redistribution of game assets. The posture is the same as for Elden Ring: read a legitimately owned install
read-only, publish derived facts (timings, sizes, damage numbers), and treat models and animations as copyrighted art.
Committing exported `.glb` files to a public repo carries the same risk as the Elden Ring models already in
`models/elden-ring/`, so decide that once for both.
