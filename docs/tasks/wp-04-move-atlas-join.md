# WP-04: Join moves and atlas entries

**Status:** Suggestion · **Priority:** P2 · **Depends on:** none

## User task and intended outcome

*Find relevant examples* and *compare approaches.* From an atlas entry (for example "Sprint attack"), a learner can
open the exact Elden Ring move behind its clip. From a move, they can reach the atlas entry and see how other games
handle the same action.

## Basis

**Stated goal**
- Help learners compare how different games handle comparable actions (`CLAUDE.md`).

**Observed problems** (inventory §6)
- **The link is only in a build file.** The move behind each Elden Ring render is recorded only in
  `tools/er_gifs/jobs.json` and is not carried into `library.json`.
- **Move deep links don't work.** `fromHash` reads game, family, class, weapon, types, grip and sort, but no move
  (`frame-data.html:535-540`), so a link cannot open a specific move.
- **The atlas game filter misses most renders.** 28 of the 36 entries with an Elden Ring render do not list Elden
  Ring in `example_games`, and the filter reads only that field.
- **Curation records are stale in places.** For example, `gif-screening.json` has duplicate `removed`/`added`
  names, entries listed as missing references that now have them, and inconsistent "Shadow of the Erdtree"
  spelling.

**Assumptions to test**
- `class` + move `id` is a sufficient join key (118 ids repeat across classes, so the id alone is not).

## Proposed scope

1. Carry `class` + move id from `jobs.json` into each render clip in `library.json`. Do this through the importer
   (`tools/er_gifs/add_to_library.py`) so rebuilds keep it.
2. Support `m=<class>|<id>` in the Frame Data hash: open that move in the preview or inspector.
3. On atlas clips with a move id, add "Inspect frame by frame" linking to that move.
4. In the inspector, show "Illustrates: <atlas entry>" (WP-03).
5. Fix the Elden Ring game filter: derive the game from clips and references as well as `example_games`, or
   backfill the field. **Parked (2026-10-24):** Sungkuk set this aside because improving Action Atlas is not
   the current goal. A view-only version was built and discarded: the filter also read clip games (Elden Ring and
   its expansions only), so Elden Ring matched 63 entries instead of 34 and Shadow of the Erdtree was listed
   under it. Revisit if Atlas work is adopted.
6. Clean up the stale curation records listed in inventory §6.7.

## Out of scope

- Joining moves for games other than Elden Ring.

## Open questions

- Should a Common animation (locomotion, reactions) link the same way? That depends on WP-07.

## Done when

- Every Elden Ring render clip with a source move opens that move in Frame Data in one click.
- Filtering the atlas by Elden Ring shows all entries with an Elden Ring render (parked, see scope item 5).
- `python merge.py` and `build_page.py` keep the new fields after a rebuild.

## Evidence to capture

- Atlas entry with the new link, and the move it opens.
