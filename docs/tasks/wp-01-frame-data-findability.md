# WP-01: Find a move by what it is

**Status:** Suggestion · **Priority:** P1 (first focus) · **Depends on:** none

## User task and intended outcome

*Find relevant examples.* A learner who wants to study "a jumping heavy with a greatsword" or "a running attack"
should reach a short list of matching moves in a few steps, without knowing Elden Ring's internal naming.

## Basis

**Stated goal**
- Sungkuk: "First, I will focus on improving the Frame Data viewer. It is really difficult to find the animation I
  want in this page."

**Observed problems**
- **Search works only on internal words.** It matches a per-move string built from move name, class, move type,
  damage type, input and weapon names (`frame-data.html:343`, filtered at `:359`). Move names copy Frame Data
  Explorer's convention ("1h R1 1"), so plain words such as "sprint attack", "jump attack", "R2" or "roll attack"
  either miss or rely on luck.
- **The page asks for a weapon class first.** The landing view is 40 weapon class tiles grouped by family
  (`renderIndex`, `frame-data.html:398`). Someone who starts from an action ("I want to see a running attack") has
  to pick a weapon first or scroll the long all-classes table.
- **The action filters are in the side rail.** Move types (Light chain, Heavy, Running, Jumping…) exist, but they
  sit in the left rail as a long list. On first view they are visually secondary to the weapon tiles (see
  the Frame Data first screen at commit `e98edb6`).
- **The move id is nearly hidden.** It is the key that joins every dataset, but it appears only in the details
  sheet footer (inventory §6.6).

**Assumptions to test**
- Learners mostly arrive with an *action* in mind (attack type, situation) more often than a specific weapon.
- A small synonym layer covers most real queries, so free-text search over atlas vocabulary is not needed.

## Proposed scope

1. **Plain-language search.** Add a synonym and alias layer on move types, grips and inputs. For example, R1 /
   light / attack; R2 / heavy / strong; running / sprint / dash; jumping / jump / aerial; two-handed / 2h;
   powerstance / paired / dual. Include the move id so instructors can paste one.
2. **Action-first entry point.** Show move type choices at the top of the landing view, next to or above the
   weapon tiles, so "what kind of move" and "which weapon" are equal starting points.
3. **Readable move labels.** Show a plain description next to each internal name, for example "1h R1 1" →
   "One-handed light attack, 1st in chain". Keep the original name for people who know the convention.
4. **Clear feedback.** Show the active query and filters with counts, and give an empty state that suggests the
   nearest match or which filter to drop.

## Out of scope

- Search across other games or the atlas page (later, if this works).
- Changing the extracted data or move type classification.

## Open questions

- Which queries do real users type? (Sungkuk: collect 10–20 example questions from Discord or class use.)
- Should weapon names (455) autocomplete, or stay as tiles?

## Done when

- A defined list of test queries (at least: "sprint attack", "jump heavy greatsword", "R2 katana", "roll attack",
  "backstab", a pasted move id) each returns the intended moves at the top.
- From the landing view, a user can reach "all running attacks" in one click.
- Before/after task timing on 3–5 of those queries is recorded (even informal), and the report separates "works"
  from "measurably easier".

## Evidence to capture

- `after/frame-data-viewport.png` (landing view), plus a search result screenshot for one test query.
