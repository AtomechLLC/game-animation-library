# Scouting: Ninja Gaiden Black

Can we do for Ninja Gaiden Black (Xbox, 2005) what the other importers do: per-move frame data for Ryu (startup,
active, recovery, cancels), a docked preview with hitboxes, and library clips? Checked on 2026-10-24 against a USA disc
image (title ID `5443000D`), read-only. The starting point was [Ninja Gaiden Black Recompiled](https://github.com/gamboozino/ngbrecomp)
by gamboozino, a static recompilation of the game; it carries no game data.

**Verdict: yes for frame data, with real reverse-engineering work for the preview.** Ryu's moves are timeline scripts
with frame numbers in them, uncompressed, and the attack on/off events read straight out of them. Nothing is encrypted
or compressed. But no community tools or format notes exist for this game, so every format below was worked out from
the bytes, and moves have no names in the data: telling which script is which move needs the animation on screen.

## The disc

- The game is `default.xbe` plus about 240 `.afs` archives (CRI's AFS: a count, then offset/size pairs, then a name
  table of 48-byte records). `chr_*.afs` hold characters, `cmn.afs` the always-loaded data, stage archives the rest.
- The image checked is **media-patched** (patched so a modded Xbox boots it from a burned DVD): `default.xbe`'s `.text`
  and `.rdata` hash to `96194e57cc5fb985` and `cac4f1e9efa0c5ac` (FNV-1a 64), the same copy as
  [ngbrecomp#2](https://github.com/gamboozino/ngbrecomp/issues/2). The recomp checks those sections and refuses it, so
  it cannot run from this image. The `.afs` data is untouched by the patch, so extraction does not need the recomp.
  A clean retail or Redump image would let the recomp run for checking timings in game.
- The recomp's toolkit still helps: `xboxrecomp/tools/disasm` splits the XBE into 9,753 functions with cross
  references, which is where opcode meanings can be confirmed.

## Where Ryu's combat data lives (`cmn.afs`)

| File | What it is |
|---|---|
| `ryu.mtn` (1.3 MB) | `chr_dat` container: section 0 Ryu's shared motions, section 1 **2,297 timeline scripts** (one per state, every weapon), section 2 a small trailer |
| `rm_kt.mot`, `rm_nc.mot`, `rm_hm.mot`, `rm_yt.mot`, `rm_mg.mot`, `rm_ro.mot` | Weapon motion banks (Dragon Sword, nunchaku, Warhammer, ...); a script asks for motion `10000 + n` from the equipped weapon's bank |
| `rs_*.mot`, `rn_*.mot` | Projectile weapon and ninpo motions |
| `ryu.chr` | `chr_dat2`: body collision shapes per bone (spheres and capsules: type `0x91000001`/`2`, bone, offsets, radii in metres), and a large table that looks like the input/combo graph (state id, condition, flags) |
| `katana.itm`, `nchak.itm`, `hammer.itm`, `hand.itm`, `body.itm`, ... | `itm_dat2`: weapon and limb attack shapes, e.g. the Dragon Sword's blade as capsules on bone `0x20` |
| `ryu.kmd` (in `chr_ryu.afs`, plus costumes `chr_ryua-g.afs`) | The model: an `OBJINFO` chunk with 59 bones (`OI` records with translation, rotation, scale), then meshes |

`chr_e_ryu.afs` holds the same layout for the "enemy Ryu" fight (`e_ryuk.mtn` per weapon, `e_ryu.chr`); 1,761 of its
scripts are byte-identical to the player's, so it is a second source to cross-check.

## The timeline scripts

Each script is a list of 16-bit words, `3 <motion> <n>` first and `0xffff` last. `0 <frame>` waits for that frame
of the motion; the commands after it run then. With fixed lengths per opcode (`0x04`, `0x13`, `0x15`, `0x17`, `0x23`:
six words; `0x14`, `0x21`: four; `0x0d`, `0x0e`, `0x18`, `0x1f`: three; `0x07`, `0x08`, `0x11`, `0x1b`: one; the rest
two), 2,281 of the 2,297 scripts parse end to end. Script 400 (a Dragon Sword attack) reads:

```
0 6   13 0 0 15 1 0      0 7   13 0 0 15 0 0
0 9   d 0 1              ; attack slot 0 on  (frame 9)
0 a   e 2100 0           ; swing sound
0 c   13 2 4 1 3 0       ; input window
0 d   d 0 0              ; attack slot 0 off (frame 13): 4 active frames
0 2c  9 0
0 2f  13 2 4 1 ffff ffff ; any input accepted from here
0 31  ...                ; end of script at frame 49
```

So startup and active frames come from the `0x0d` events (slot, 1 = on, 0 or 4 = off; slots other than 0 are
kicks and other limbs), and the cancel windows from the `0x13 2 4 ...` input events. The exact meaning of each
`0x13` sub-command still has to be confirmed in the game code.

## The motions

A motion is 44 track offsets (one per animated channel), then one track per channel: keys of 32 bits, the high
16 bits a value that moves smoothly from key to key (most likely a binary angle, 65,536 = one turn, with 4 more bits
of fraction), the low 12 bits a duration (`5` on every key of a sampled track, `0` on the last). Script 400's events
run to frame 49 and its motion has 60 keys of `5`, so `5` is probably one 60 fps frame; to be confirmed. Constant channels are a single key. Which bone and axis each of
the 44 channels drives is not known yet; the model has 59 bones, so the mapping is part of the KMD or the `.chr`.

## What is left, and effort

1. Name the moves: script ids carry no names. Rendering each motion (step 3) and matching it to the manual's move
   list is the realistic way; the combo table in `ryu.chr` gives the button sequence leading to each state.
2. Confirm the opcodes against the code (the `0x13` input windows, slots of `0x0d`, the end-of-recovery marker).
3. KMD meshes and the channel-to-bone mapping, for a 3D preview like Elden Ring's with the `.itm` capsules drawn on.

Frame data for Ryu's Dragon Sword moveset with names is about 2 to 3 days of work; the 3D preview with hitboxes
another 3 to 5 days, most of it the model format.
