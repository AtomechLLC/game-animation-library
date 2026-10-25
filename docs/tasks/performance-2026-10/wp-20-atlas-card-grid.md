# WP-20: Still posters on Action Atlas cards

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-12

## User task it protects

*Find relevant examples.* The Action Atlas card grid is the front door of the library. It should appear quickly and
scroll smoothly so visitors browse the categories, and searching should keep up with typing.

## Basis

**Observed problem**
- **Every card thumbnail is the full animated clip.** `thumbOf()` (`template.html:295-299`) picks a clip from
  `gifs/`, and each card's `<img class="thumb" loading="lazy">` (around `template.html:415`) loads it. There is no
  still image.
  - 321 cards have a thumbnail; together they are **73 MB** (median 157 KB). Clips have a median of 60 frames and up
    to 420.
  - Chrome starts lazy images well before they scroll into view, so the first desktop screen probably pulls 30–60
    clips (about 5–10 MB).
  - Every visible card keeps decoding its animation, which costs CPU and battery.
  - The clips are about 200 px wide but stretched into cards at least 230 px wide, so they look soft.
- **Search rebuilds the whole grid on every keystroke.** `#q` calls `render()` on each `input` with no debounce
  (`template.html:464`). `render()` (`template.html:395-417`) filters the full list five times, reads layout between
  writes in `placePlayhead()`, and replaces the grid's `innerHTML`, which recreates every `<img>` and restarts every
  animation. `thumbOf` runs twice per card and sorts that entry's clips each time.
- **The inlined data carries about 195 KB the page never uses** (`build_page.py`; `server.js:24-37`):
  `rejected_gifs` (64 KB), per-clip `screened` (48 KB), `source_url` (70 KB, only community items use it) and
  `search_query` (13 KB). The page parses it all (`template.html:264`).

**Assumptions**
- A still frame shows enough to recognise an action in the grid; the motion matters once a card is hovered,
  focused or opened.

## Proposed scope

1. Generate one small still WebP poster per card clip (first or most representative frame, about 5–15 KB) in the
   build, and use it as the card image.
2. Play the animated clip on hover or keyboard focus, and in the detail sheet.
3. Debounce search (100–150 ms); compute the thumbnail once per card; show and hide existing cards instead of
   rebuilding them, so images are not recreated.
4. Leave unused fields out when `build_page.py` and `server.js` inline the library (the source `library.json` is not
   changed).

## Out of scope

- Changing which clip represents a card, or the card layout.
- Changing `library.json` itself.

## Open questions

- Posters are a new kind of generated file. Commit them to `gifs/` (or a `posters/` folder), or generate them during
  the Pages build? This interacts with WP-23.
- First frame or a chosen frame? A curated frame is better for learning but needs a field per clip.

## Metric

- Bytes after the first screen and after scrolling the whole grid: about 5–10 MB and 73 MB → under 1 MB and about
  5 MB.
- Long tasks while typing a ten-character search: baseline → none over 50 ms.
- CPU over ten idle seconds on the first screen: baseline → near zero.
- Action Atlas HTML size: 837 KB raw / 182 KB gzipped → about 640 KB raw.

## Done when

- The grid shows posters, plays the clip on hover and focus, and the detail sheet is unchanged.
- Search results match the current behaviour.
- Measured against the WP-12 baseline on GitHub Pages and the Node host.
