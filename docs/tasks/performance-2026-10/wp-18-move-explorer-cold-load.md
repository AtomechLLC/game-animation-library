# WP-18: Shorter first-load chain in Move Explorer

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-12, WP-13 (soft)

## User task it protects

*Find relevant examples* and *use examples in teaching*. Opening a teaching link (WP-05) or the app itself should
show a move quickly, also on a school connection.

## Basis

**Observed problem**
- **About 5 MB before the first 3D frame** on Elden Ring, the default game, most of it the 3.5 MB armor model
  (`armor-raging-wolf.glb`, including a 1.12 MB PNG texture).
- **A serial chain of about eleven steps:** page → `games.json` + `stores.json` → `elden-ring.json` (1.55 MB) +
  `icons.json` → `renderAll` → `dock` → `import('viewer3d.js')` → three.js from jsDelivr → `GLTFLoader.js` →
  navigation and speed modules → `models.json` → class `moves/*.json` → armor model → weapon model and animation.
  Each step waits for the one before (`frame-data.html:513`, around 779-790; `frame-data/viewer3d.js:142`).
- **The example viewer is built eagerly**, before any class is picked, even when the dock is not on screen
  (`dock()`, around `frame-data.html:779-790`).
- three.js r0.160 is loaded as the unminified `three.module.js`.
- No `modulepreload` or `preload` hints exist.
- A game switched away from and back to is fetched again (no in-memory cache of game data).

**Assumptions**
- Showing the example move early is valuable (WP-02), so the goal is to start it sooner, not to drop it.

## Proposed scope

1. `<link rel="modulepreload">` for three.js, `GLTFLoader` and `viewer3d.js`; `<link rel="preload">` for
   `games.json` and the default game's JSON. Start fetching `models.json` and the first class file in parallel with
   the game JSON instead of after it.
2. Load the minified three.js build.
3. Build the example viewer when the dock is on or near the screen.
4. Keep loaded game data in memory for the session so switching back is instant.

## Out of scope

- Re-exporting the armor model with a smaller texture or mesh compression. It would save most of the 3.5 MB but
  changes a media file; see open questions.

## Open questions

- Should the armor model be re-exported (WebP or KTX2 texture, meshopt compression)? That is a media change that
  needs its own decision, and possibly a change to `tools/frame_data/`.

## Metric

- Cold Elden Ring load, throttled (WP-12 setup): time to the first 3D frame and the length of the request chain.
  Target: the chain shortened by at least three steps.
- Switching to another game and back: second load bytes → 0.

## Done when

- The waterfall shows the three.js modules, game JSON and model manifest loading in parallel.
- Every game still opens and shows its preview.
