# WP-06: Hide or relabel unreliable fields

**Status:** Suggestion · **Priority:** P1 (small) · **Depends on:** none

## User task and intended outcome

*Observe deliberately* and *use examples in teaching*, accurately. Learners and instructors should not see empty or
mislabelled values presented as facts.

## Basis

**Stated goal**
- Continually improve relevance, clarity and accuracy, and replace misleading material (`CLAUDE.md`).

**Observed problems** (inventory §5.4)
- **`iframes` is always empty.** It is empty on all 3,865 moves, yet the strip legend, details sheet and HUD
  reserve space for it.
- **`damage.poise` is never present.** The default Poise column always shows "—".
- **`total` is mislabelled.** It is called "animation length" in the README and column tooltip, but it is the end
  of the last cancel window. It matches the clip length on only 13 of 3,511 comparable moves.
- **Some moves lack data.** 476 buffed moves have no damage, and 352 jumping moves have no recovery, total or
  cancels. Both show as "—" without explanation.
- **`parry` has no moves.** The move type is listed, but no moves use it.

## Proposed scope

1. Hide `iframes` and Poise for Elden Ring until the data has them. Hide per game, not globally: other games may
   have the data.
2. Rename `total` to what it measures (for example "Cancel window ends"), and correct the README and tooltip. If
   the clip length is wanted, read `frames` from the move files.
3. Explain the missing values where they occur ("No recovery data for jumping attacks"; "Damage not extracted for
   buffed moves").
4. Drop empty move types from filters (already partly done by count filtering; confirm for `parry`).

## Out of scope

- Re-extracting data to fill the gaps (a separate data task, for example via `import_er_nyasu.py` for poise).

## Done when

- No Elden Ring view shows a column, band or field that is empty for every move.
- The label for `total` matches its computation in the page, the README and `frame-data/README.md`.

## Evidence to capture

- Table header and details sheet, before and after.
