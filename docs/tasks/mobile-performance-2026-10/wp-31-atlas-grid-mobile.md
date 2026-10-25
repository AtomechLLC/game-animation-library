# WP-31: Action Atlas grid on phones

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-25, WP-20

## User task it protects

*Find relevant examples.* The Action Atlas is the front door of the library, also for visitors who arrive from a
link on a phone. The grid should appear quickly, scroll smoothly and not eat through a cellular plan.

## Basis

**Observed problem**
- **Every card is a full animated clip, on phones too.** Each card's `<img class="thumb" loading="lazy">`
  (`template.html:415`) is an animated WebP from `gifs/`. Of the WebPs there, 845 of 846 with an extended header are
  animated: median 200 × 148 px and 60 frames, p90 191 frames, up to 420. The 321 card thumbnails total 73 MB.
  WP-20 replaces them with still posters; this package covers what remains specific to phones.
- **Decoding cost scales with how many cards animate.** One frame of every thumbnail decoded is about 44 MB; decoding
  each card's full animation for the whole grid would be several gigabytes. Each visible card keeps animating, and
  nothing pauses cards that scrolled away. On desktop, idle with animated cards on screen, the GPU process used 159 ms
  of CPU per second.
- **Phones load more ahead than they show.** At phone width the grid has one column (`template.html:108`) and about
  1.5 cards fit on screen, but Chrome's lazy-loading margin on cellular is 1,250–2,500 px, so about 4–8 clips (about
  1 MB) load before the first scroll.
- **Thumbnails are upscaled on phones.** The median clip is 200 px wide and shown about 358 CSS px wide at pixel
  ratio 3. A still poster for phones could be sharper without being larger in bytes than today's clip.
- **Reduced motion is ignored for clips.** `prefers-reduced-motion` affects only the playhead
  (`template.html:90,479`); card and detail-sheet clips keep animating.
- **The page does all its work at once.** The whole `library.json` is inlined (`index.html` 837 KB, 182 KB gzip),
  parsed, and all 330 cards are written in one `innerHTML` (`template.html:413`). With 4× CPU, the desktop baseline
  blocked for 3.6 s on a cold load (longest task 2.1 s). A mid-range phone is about that slow.
- **Missing image hints.** No `decoding="async"`, `width` or `height` on card images (the `aspect-ratio` CSS keeps the
  layout steady). The window `resize` handler (`template.html:474`) runs on every event; iOS fires resize as its
  toolbar collapses while scrolling.

**Assumptions**
- WP-20 (still posters, debounced search, no rebuild of the grid) is adopted first; most of the cellular saving comes
  from it.
- On touch there is no hover, so WP-20's "play on hover" needs a touch equivalent.

## Proposed scope

1. On touch devices, play a card's clip only when the learner asks for it (a tap opens the detail sheet, as today) or,
   if Xelnath prefers, only for the one card nearest the centre of the screen. Never more than one animated card at a
   time on a phone.
2. Respect `prefers-reduced-motion` and Save-Data: posters only in the grid; clips in the detail sheet start paused.
3. Posters sized for pixel ratio 2–3 at phone width (`srcset` with two widths), with `decoding="async"`, `width` and
   `height`.
4. Render the first screen of cards first and the rest in the next idle period, so the page becomes usable sooner on
   a slow CPU; coalesce the `resize` handler to one call per animation frame.

## Out of scope

- Changing the grid's layout or what cards show.
- Generating posters (WP-20).

## Open questions

- On touch, should the grid be stills only, or play the card nearest the centre of the screen?
- Poster widths for `srcset` (for example 360 and 720 px) add generated files; decide together with WP-20.

## Metric

- Emulated phone, WP-25: cold first screen and full-grid scroll, bytes and requests; baseline → posters only, under
  1 MB for the first screen.
- Decoded image memory and GPU process CPU while idle mid-grid: baseline → one animated card at most.
- Blocking time on a cold load at 4× and 6× CPU: baseline → under 1 s.
- Real iPhone, WP-25 checklist: scroll the whole grid without a reload.

## Done when

- On phones, at most one card animates, reduced motion and Save-Data show stills only, and the full-grid scroll stays
  within the targets above.
- Desktop behaviour matches WP-20's.
