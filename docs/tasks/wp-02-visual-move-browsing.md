# WP-02: Recognise moves visually before opening them

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-01 (soft)

## User task and intended outcome

*Find relevant examples* and *observe deliberately.* Once a list is narrowed, a learner should recognise the move
they mean by seeing it, not by opening moves one by one.

## Basis

**Stated goal**
- Finding a specific animation is hard (Sungkuk, Discord thread).

**Observed problems**
- **The 3D preview appears only in a class view.** `dock()` turns the preview off unless a weapon class is selected
  (`frame-data.html:500-502`). The all-classes table, where search results land, has no visual preview at all.
- **Table rows are mostly numbers.** The phase strip shows the timing shape, but there is no image or motion
  thumbnail, so similar names ("1h R1 1", "1h R1 2") look alike.
- **Hover only prefetches.** With the dock open, hovering a row prefetches the animation, and the preview changes
  only on click (`frame-data.html:574`, `:545`).

**Assumptions to test**
- Seeing the motion is the fastest way to confirm "this is the one".
- Pre-rendered thumbnails would cost too much storage for all 3,865 moves. A live preview of the focused row is
  enough.

## Proposed scope

1. **Preview from any list.** Show the preview for the selected row in the all-classes view too. Load the class
   data the row needs when it is not already loaded.
2. **Preview follows focus.** Moving through rows with arrow keys or focus updates the preview, with a short delay
   to avoid thrashing.
3. **Legend that explains the strip.** Keep the phase legend near the table and connect the strip colours to
   design terms (anticipation, contact, commitment).

## Out of scope

- Rendering a thumbnail or GIF for every move.
- Redesigning the viewer itself (WP-03).

## Open questions

- Performance: what is the load cost when switching classes often (class move files plus models)?
- On small screens, should the preview be a sheet instead of a dock?

## Done when

- From a search result in the all-classes table, selecting a row shows that move's animation without picking a
  class first.
- Keyboard users can step through rows and see the preview follow.

## Evidence to capture

- `after/frame-data-search-preview.png`: search results with the preview open.
