# WP-37: Shared helpers and one meaning for frame data

**Status:** Suggestion · **Priority:** P1 · **Depends on:** none

## User task it protects

*Compare approaches.* Move Explorer shows one move; Trends compares many moves across games. When both use the same
move, they must agree about it, or a student comparing a number in Trends with the move in Move Explorer finds two
answers.

## Basis

**Observed problem**
- `lastActive` (the last active frame of a move) is written twice and the copies already disagree
  ([report, section 7](../../reports/duplicated-app-code.md#7-small-script-helpers)):
  - `frame-data.html:493` returns `0` for a move with no active frames;
  - `trends.html:288` returns `null`, and also accepts a move with no `active` list at all.
  Trends then leaves such a move out of its spans (`trends.html:300`), where Move Explorer treats it as ending at
  frame 0.
- Trends reads the same per-game files as Move Explorer and recomputes other meanings from them too, so any rule
  about what the data means can drift the same way.
- Smaller copies: `$` (query one element) and `esc` (escape text for HTML) are identical in all three apps
  (`template.html:372–373`, `frame-data.html:452–453`, `trends.html:223–224`). `writeHash` and `fromHash`
  (link state) follow one pattern in Move Explorer (`frame-data.html:822, 841`) and Trends (`trends.html:527, 529`)
  but with different fields.

- This is not rare. Moves with an empty `active` list, counted from the per-game files at `7310cb2`: Super Smash
  Bros. Ultimate 1,444 of 3,589, Street Fighter III: 3rd Strike 270 of 1,303, Hollow Knight 46 of 90, Devil May Cry 3
  2 of 118; none in Elden Ring, No Rest for the Wicked or Ninja Gaiden Black. 1,762 moves in all. No move lacks the
  `active` list entirely, so Trends' extra check is unused today.

**Assumptions**
- Most of these moves are not attacks (movement, stances, specials without a hitbox), so they may already be outside
  what Trends compares. Whether any of them reaches a Trends number is checked in step 1, not assumed.

## Proposed scope

1. Check which of the 1,762 moves with no active frames reach a Trends number or a Move Explorer view (timeline end,
   cancel windows). Decide what "last active frame" means for them and which of the two answers is right.
2. A small shared module for frame data meanings, used by both Move Explorer and Trends: `lastActive` first, then any
   other value both apps derive from the per-game files (an inventory of these is part of the work).
3. Share `$` and `esc` from `shared/` (or leave `$` copied: it is one line and never changes; `esc` matters more,
   because every app relies on it to keep data out of the markup).
4. Leave `writeHash` and `fromHash` per app: their fields differ by design. Only a shared reading helper, if it
   removes real repetition.

## Out of scope

- Changing the per-game data files or their format (`frame-data/README.md`).
- Changing what Trends compares, other than following the decided meaning.

## Open questions

- For a move with no active frames, which is right: "ends at frame 0" (Move Explorer) or "no end" (Trends)?
- Do Action Atlas and Trends need `esc` behaviour beyond what it does today (for example attribute-safe quoting)? If
  so, decide once in the shared copy.

## Metric

- Definitions of `lastActive`: 2 (disagreeing) → 1.
- Moves where Move Explorer and Trends disagree about the last active frame: count from step 1 → 0.
- Copies of `esc`: 3 → 1.

## Done when

- Move Explorer and Trends import the same `lastActive` and give the same answer for every move.
- Trends' numbers are compared before and after; any change is explained by the decided meaning.
- The three apps render and escape text as before (a name with `<`, `&` and quotes shows as text in each).
