# WP-17: Re-render only what changed

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-12

## User task it protects

*Find relevant examples.* Filtering by class, weapon, type, grip and startup is how learners narrow thousands of
moves to the ones they are studying. Each click and slider drag should answer at once.

## Basis

**Observed problem**
- **`renderAll()` rebuilds the whole app on every interaction** (`frame-data.html:542-575`). Every click on a game,
  family, class, weapon, type, grip, sort, toggle or "clear" calls it. One call:
  - runs `pool()` six times over all moves (type, grip, armor, multi, no-parry counts, plus `renderTable`) and the
    dock filters once more; `pool` re-splits the search text per move;
  - runs `legendHtml` with up to five `D.moves.some` scans;
  - rewrites with `innerHTML`: the game bar, the ruler (89 buttons for Super Smash Bros. Ultimate, then a forced
    layout in `placePlayhead`), types, grips, classes, the class index, weapons, the table, the Moveset Inspector,
    store links and the footer.
- **The startup slider is not throttled:** `#maxStart` calls `renderAll` on every `input` event
  (`frame-data.html:894`), so a drag runs dozens of full rebuilds a second. Search is debounced at 120 ms (good).
- **The class view builds the move table twice.** `renderTable` fills both the Moveset Inspector (`#mlist`) and the
  full grouped table (`#table`), and CSS hides `#table` while the dock is open (`frame-data.html:318`). `setWide`
  (Tab, `frame-data.html:687`) re-runs the whole `renderTable`.
- **Animated Street Fighter III icons are recreated on every render.** They are animated WebP (`remy.webp` 536 KB,
  331 frames) shown at 22–64 px in class tiles, table rows and the inspector.

**Assumptions**
- The no-class view is paginated at 150 rows (`PAGE`), so list virtualization is not needed yet.

## Proposed scope

1. Throttle the startup slider to one render per animation frame.
2. Compute all facet counts in one pass over the base pool.
3. Render only the sections whose inputs changed. The game bar, footer and store links change only in `loadGame`.
4. Skip building `#table` while the dock hides it; build it when "Hide" is pressed.
5. Use a still first-frame icon in lists and keep the animated icon for the large title (needs still icons; see open
   questions).

## Out of scope

- Changing filters, layout or what is shown.
- Virtualizing lists.

## Open questions

- Still Street Fighter III icons are new generated files. Generate them in the importer, or extract the first frame
  in the browser with `ImageDecoder`?

## Metric

- `renderAll` duration for a class click and a weapon click (Elden Ring): baseline from WP-12 → about a third.
- Long tasks during a two-second startup slider drag: baseline → none over 50 ms.
- DOM node count after picking an Elden Ring class: baseline → without the hidden `#table`.

## Done when

- Every filter gives the same results and counts as before (checked on Elden Ring and Super Smash Bros. Ultimate).
- The slider drag and class clicks show no long tasks in the Performance panel.
