# WP-15 result: the 3D viewer renders only when its picture changes

Before and after for [WP-15](../../tasks/performance-2026-10/wp-15-viewer-render-on-demand.md).

- **Before:** the idle section of the [baseline](baseline.md), measured on the live GitHub Pages site (`23fbc61`).
- **After:** three runs of `node tools/perf/baseline.mjs --only idle --base http://127.0.0.1:8765/`, measured
  against a local copy of branch `perf/wp-15-render-on-demand`. The raw data is in
  [`wp-15-after-2026-10-25.json`](wp-15-after-2026-10-25.json).
- **Same conditions:** same machine, Chrome 155 headless, same script. Idle cost does not depend on the network, so
  a local copy is a fair comparison.

## Read this first

- **Frame rates are not capped.** Headless Chrome runs animation frames at 160–230 per second, while a 60 Hz
  monitor runs 60. Compare states and before/after with each other, not with a monitor.
- **The floor is about 20 ms, not 0.** The measuring script runs its own animation-frame loop, which costs about
  20 ms of main thread per second. An idle viewer can read no lower than that.
- **What "renders per second" counts:** animation frames that contained a WebGL draw.

## 3D viewer (Elden Ring, Greatsword, 5 s per state)

| State | Renders/s, before → after | Draw calls/s, before → after | Main thread busy/s, before → after (three runs) | Renderer + GPU process CPU/s, before → after (three runs) |
|---|---|---|---|---|
| Playing at 0.5× | 228 → **15** | 5,980 → **394–399** | 127 → 83–88 ms | 248 + 338 → 126–149 + 67–71 ms |
| Paused | 171 → **0** | 4,456 → **0** | 88 → 24–28 ms | 173 + 350 → 47–58 + 24–30 ms |
| Folded ("Hide"), paused | 167 → **0** | 4,337 → **0** | 60 → 21–25 ms | 80 + 97 → 28–37 + 27–47 ms |
| Hidden (no move matches), paused | 162 → **0** | 4,222 → **0** | 70 → 13–22 ms | 113 + 92 → 31–48 + 16–25 ms |
| Example scrolled off screen, paused | 199 → **0** | 5,164 → **0** | 116 → 18–24 ms | 163 + 108 → 26–54 + 20–29 ms |

- **Paused, folded, hidden and off screen:** the viewer renders nothing. Its main-thread cost drops to the
  instrumentation floor.
- **Paused and visible:** the GPU process's CPU time falls from about 350 ms to about 25–30 ms per second.
- **Playing:** the viewer renders only when the pose changes. At the default 0.5× speed, a 30 fps move changes
  pose 15 times a second, so the old loop drew the same picture about 15 times over. Learners see the same
  animation as before.

## Sprite and clip viewers

These viewers were not changed; WP-15 left them alone. Their numbers stayed within run-to-run noise:

| Viewer | State | Before | After (three runs) |
|---|---|---|---|
| Sprite sheets (Street Fighter III, Ryu) | Playing | 30 frames/s, 94 ms main thread | 30 frames/s, 85–104 ms |
| | Paused, folded, hidden, off screen | 0 frames/s, 21–29 ms | 0 frames/s, 19–31 ms |
| Clips (Super Smash Bros. Ultimate, Kazuya) | Playing | 15 frames/s, 50 ms | 15 frames/s, 50–59 ms |
| | Paused, folded, hidden | 0 frames/s, 20–23 ms | 0 frames/s, 16–27 ms |

## Behaviour checks

**Renders after each action.** A headless script counted renders in the second after each action, with the move
paused.

| Action | Renders |
|---|---|
| Pause | 0 |
| Paused idle (2 s) | 0 |
| Frame step `.`, `→`, Shift + `→`, Ctrl + `←` | 1 each |
| Scrub | 1 |
| Grid `Z` on and off | 1 each |
| Bounds `B` on and off | 1 each |
| Fit to view `F`, default camera `D`, Numpad 1 | 1 each |
| Wheel zoom | 1 |
| Drag orbit (10 moves) | 10 |
| Hitboxes, ghost hitboxes and root motion checkboxes | 1 each |
| Window resize | 1 |
| Copy-link `setView` | 1 |
| Weapon switch | 1 |
| Move switch (Down) | 1 |
| Fold (Hide) | 0 |
| Unfold | 1 |

**While playing:**
- **Fold:** one render, then the loop stops. Unfolding resumes playback.
- **Hidden** (a search that matches no move): the loop stops. Clearing the search resumes playback.
- **Scrolled off screen:** the example viewer stops. Scrolled back, it plays again.

**Other checks:**
- **Other 3D games:** No Rest for the Wicked, Ninja Gaiden Black and Devil May Cry 3 play normally.
- **No stale picture,** in headed Chrome: paused at frame 30, then pressed `Z`, `B` and ten frame steps. Each
  change showed at once. The render stats overlay read 0 loop ticks and 0 renders per second while paused.
- **GIF renderer** (`tools/er_gifs/render.html`): `ER.show`, `ER.grid(false)`, `ER.seek(10)`, `ER.step()` and a
  weapons-hidden `ER.show` each produced a different `ER.frame()` image. It asks the viewer to render after its
  own scene changes with the new `view.requestRender()`.
- **No console errors** in any check.
