# Performance baseline, 2026-10-25

The "before" measurements for the performance round. [WP-12](../../tasks/performance-2026-10/wp-12-performance-baseline.md)
produced them. Later packages (WP-13 to WP-24) compare against these numbers, measured the same way.

- **Raw data:** [`baseline-2026-10-25.json`](baseline-2026-10-25.json)
- **Script:** [`tools/perf/baseline.mjs`](../../../tools/perf/baseline.mjs)
- **Site measured:** the live GitHub Pages site, https://atomechllc.github.io/game-animation-library/.
  - It was deployed from commit `23fbc61` (PR #80, workflow run 40201887374).
  - The run took from 14:54 to 15:09 UTC. The script checked the deployment before and after, and the site did not
    change during the run.

## How it was measured

**Host.** GitHub Pages is the production host.
- Every push to `main` deploys there (`.github/workflows/static.yml`).
- The repository variable `LIBRARY_API_URL` is not set, so the public pages do not use the Node host.
- The Node host measurements in the WP-12 scope were therefore left out.

**Setup**

| Item | Value |
|---|---|
| Browser | Chrome 155.0.8059.85, headless, 1440 × 900 window, device scale 1 |
| Machine | Intel Core Ultra 9 275HX, 64 GB memory, Windows 11 |
| WebGL | ANGLE on the integrated Intel Graphics (Direct3D 11) |
| Unthrottled | this machine on its own connection |
| Throttled | Lighthouse's default mobile throttling: 150 ms round trip, 1.6 Mbit/s down, 750 kbit/s up, 4× slower CPU |
| Profiles | a fresh browser profile per scenario, so the first load of each scenario has an empty cache |

**Repeat it**

```
node tools/perf/baseline.mjs                       # every scenario, about 15 minutes
node tools/perf/baseline.mjs --only load,idle      # some scenarios
node tools/perf/baseline.mjs --base http://localhost:8000/ --out <file>   # another copy of the site
```

For the live site, the script records which deployment it measured. If `main` is redeployed during the run, it
prints a warning and sets `site.changedDuringRun`. Do not merge to `main` while it runs.

**What the script does**

The script loads instrumentation into each page before the page's own scripts run. It records:
- long tasks;
- paint and event timings;
- WebGL draw calls and 2D canvas `drawImage` calls, and how many animation frames contained a draw;
- decoded `ImageBitmap` bytes;
- `history.replaceState` calls;
- WebGL contexts created.

It also wraps page functions to time them: `renderAll`, `renderTable`, `preview`, `stepMove`, `dock`, the viewer's
`show`, and the Action Atlas's `render`. **The apps' code is not changed.**

**How to read the numbers**

- **Long tasks:** main-thread tasks over 50 ms.
- **Blocking time:** the part of each long task over 50 ms, summed. On a page load it counts only after First
  Contentful Paint, as Total Blocking Time does.
- **Slowest event:** the longest input-event duration. It stands in for Interaction to Next Paint.
- **Settled times** apply to asynchronous functions (`show`, `preview`, `dock`). They run until the returned
  promise resolves, so they include downloads and waiting in a queue.
- **Frame rates:** headless Chrome is not limited to the display's refresh rate. It ran animation frames at 160–230
  per second here; on a 60 Hz monitor the same loop runs 60 times a second. Compare states with each other
  (playing, paused, folded, hidden), not with a monitor.
- **Process memory** is the operating system's private memory for each Chrome process type.
- **Decoded bitmaps** count every `ImageBitmap` created, not only those still alive.
- **The instrumentation's own cost:** it runs one animation-frame loop of its own. That costs about 20 ms of main
  thread per second, so an idle page reads about 20–25 ms/s, not 0.
- **Each figure is one run.** Today's three full runs (one discarded because the site was redeployed during it)
  agreed on bytes, request counts, draw counts and memory. Times varied more: for example Trends' unthrottled cold
  First Contentful Paint read 0.9 s, 1.6 s and 6.0 s. Compare times over a few repeats, and trust only large
  differences.

## 1. Page loads

Cold means an empty cache. Repeat means navigating away and back within Pages' 10-minute cache lifetime.

### Unthrottled

| App | First Contentful Paint | Largest Contentful Paint | First 3D frame | Blocking time | Requests | Transferred |
|---|---|---|---|---|---|---|
| Action Atlas, cold | 1.06 s | 1.06 s | — | 55 ms | 29 | 4,515 KB (images 4,179 KB) |
| Action Atlas, repeat | 0.36 s | 0.56 s | — | 64 ms | 29 | 0 KB |
| Move Explorer, cold | 0.98 s | 1.65 s | 1.88 s | 295 ms | 82 | 3,181 KB |
| Move Explorer, repeat | 0.10 s | 0.46 s | 0.61 s | 217 ms | 82 | 0 KB |
| Trends, cold | 5.96 s (an outlier; see above) | 6.98 s | — | 135 ms | 13 | 692 KB |
| Trends, repeat | 0.08 s | 0.34 s | — | 101 ms | 13 | 0 KB |

### Throttled (stand-in for school Wi-Fi)

| App | First Contentful Paint | Largest Contentful Paint | First 3D frame | Blocking time | Longest task | Transferred |
|---|---|---|---|---|---|---|
| Action Atlas, cold | 1.68 s | 1.68 s | — | 3,588 ms | 2,086 ms | 4,515 KB |
| Action Atlas, repeat | 0.65 s | 0.65 s | — | 3,093 ms | 1,324 ms | 0 KB |
| Move Explorer, cold | 1.45 s | 8.39 s | **21.11 s** | 3,096 ms | 1,463 ms | 3,181 KB |
| Move Explorer, repeat | 0.42 s | 2.54 s | 3.02 s | 2,483 ms | 997 ms | 0 KB |
| Trends, cold | 1.44 s | 6.58 s | — | 1,806 ms | 1,255 ms | 692 KB |
| Trends, repeat | 0.38 s | 2.07 s | — | 1,307 ms | 1,098 ms | 0 KB |

**Move Explorer's cold transfer by type** (unthrottled):

| Type | KB |
|---|---|
| Fetched data and models | 2,532 |
| Scripts | 294 |
| Images | 169 |
| Fonts | 151 |
| Page | 34 |

**DOM size after load:** Action Atlas 3,984 nodes, Move Explorer 4,777, Trends 1,753.

### Hosting headers (checked with `curl`)

- Pages compresses HTML and JSON with gzip and sends `ETag` and `Last-Modified`. For example, `elden-ring.json` is
  1.55 MB on disk and 132 KB on the wire.
- The cache lifetime is fixed at `max-age=600`.
- `Last-Modified` is the **deployment time**, so every push to `main` changes every file's `ETag`. After any
  deployment, a returning visitor downloads all media again.

## 2. Action Atlas card grid

| Measure | Value |
|---|---|
| First screen | 29 requests, 4,515 KB |
| Scrolling the whole grid (321 cards, 17 s) | another 297 requests, **67,544 KB** |
| Total for the whole grid | about 72 MB |
| Main thread while scrolling | no long tasks |
| Idle at the bottom of the grid | no WebGL; main thread 21 ms busy per second; GPU process 159 ms of CPU per second (animated thumbnails on screen) |

## 3. Interactions

| Interaction | CPU | Long tasks | Blocking time | Slowest event | Other |
|---|---|---|---|---|---|
| Action Atlas: type "heavy atta" (10 characters, 120 ms apart) | 1× | 3 (longest 87 ms) | 59 ms | 112 ms | `render` ×10, 74 ms total; **5,656 KB downloaded** while typing |
| | 4× | 8 (longest 955 ms) | 2,000 ms | 1,128 ms | `render` ×10, 682 ms total |
| Move Explorer: drag the startup slider for 2 s | 1× | **59** (longest 157 ms) | **2,719 ms** | 24 ms | `renderAll` ×58 (1,111 ms); 58 `replaceState` calls |
| | 4× | 69 (longest 1,132 ms) | **37,093 ms** | 120 ms | `renderAll` ×58 (7,802 ms); the page stays blocked for about 35 s after a 2 s drag |
| Move Explorer: pick the Greatsword class | 1× | 0 | 0 ms | 72 ms | `renderAll` 24 ms; the viewer shows the move 136 ms after the call |
| | 4× | 4 (longest 249 ms) | 325 ms | 352 ms | `renderAll` 119 ms; the viewer shows the move 171 ms after the call |
| Move Explorer: one Down step, from key to the next move's first frame (6 steps) | 1× | — | — | — | 132–288 ms (median 167 ms) |
| | 4× | — | — | — | 87–212 ms (median 114 ms) |
| Move Explorer: hold Down for 2 s (61 key events) | 1× | 0 | 0 ms | 32 ms | 61 previews; the slowest `show` settles 292 ms after its key |
| | 4× | 21 (longest 76 ms) | 185 ms | 136 ms | the slowest `show` settles **4.0 s** after its key, because the previews queue up |

**Note on single steps.** Single-step times scatter widely between runs, and here the 4× run was even faster than
the 1× run. Some steps reuse an animation that is already loaded and some do not. Only a large change against this
range should count as an improvement.

**What the numbers say**

- **The startup slider is the worst interaction measured.** `renderAll` itself accounts for only about 20% of the
  long-task time at 1×. The rest is style and layout after the `innerHTML` rewrites, plus the viewer reloading the
  example move on each tick (`dock` settling in up to 350 ms at 1× and 3.0 s at 4×).
- **Holding Down does not block input,** but at 4× the move on screen lags the key by up to 4.0 s, because every
  step starts its own `show`.
- **`replaceState` ran once per step** (61 in 2 s). It stayed under Chrome's throttling threshold in this test, and
  no console warning appeared.
- **The class view keeps 92 rows in the hidden `#table`** next to 81 rows in the Moveset Inspector, 3,869 DOM nodes
  in total.

## 4. Idle cost of the viewers (5 s per state)

One game for each viewer kind:
- **3D:** Elden Ring, Greatsword class.
- **Sprite sheets:** Street Fighter III, Ryu.
- **Clips:** Super Smash Bros. Ultimate, Kazuya.

The "hidden" state is a search that matches no move, which hides the panel. "Off screen" is the example viewer
before a class is picked, scrolled out of view. The clip viewer has no example viewer.

| Viewer | State | WebGL frames/s | 2D frames/s | Draw calls/s | Main thread busy/s | Renderer + GPU process CPU/s |
|---|---|---|---|---|---|---|
| 3D | Playing | 228 | — | 5,980 | 127 ms | 248 + 338 ms |
| 3D | **Paused** | **171** | — | 4,456 | 88 ms | 173 + 350 ms |
| 3D | **Folded ("Hide"), paused** | **167** | — | 4,337 | 60 ms | 80 + 97 ms |
| 3D | **Hidden (no matching move)** | **162** | — | 4,222 | 70 ms | 113 + 92 ms |
| 3D | **Example off screen, paused** | **199** | — | 5,164 | 116 ms | 163 + 108 ms |
| Sprite sheets | Playing | 0 | 30 | — | 94 ms | 154 + 110 ms |
| Sprite sheets | Paused / folded / hidden / off screen | 0 | 0 | — | 21–29 ms | 47–65 + 35–68 ms |
| Clips | Playing | 0 | 15 | — | 50 ms | 83 + 47 ms |
| Clips | Paused / folded / hidden | 0 | 0 | — | 20–23 ms | 26–44 + 21–38 ms |

**What this shows**

- **The 3D viewer never stops rendering.** Paused, folded, hidden and off screen, it keeps drawing at the
  headless frame rate as when it plays, about 26 draw calls per frame. On a 60 Hz monitor that is 60 frames and about 1,560 draw calls per second.
- **The sprite and clip viewers already stop drawing when paused.** Their idle cost is at the level of the
  instrumentation itself (about 20–30 ms/s). Their animation loops keep running, but cheaply.
- **The cost is not only in the page.** When the paused 3D viewer is visible, the GPU process uses about 350 ms of
  CPU time per second on this machine.

## 5. Hover prefetch

The pointer was swept down 50 rows, 60 ms per row, without clicking.

| Where | Requests | Downloaded | Long tasks |
|---|---|---|---|
| Elden Ring, all-classes table (no class picked) | 51 | 398 KB | 0 |
| Super Smash Bros. Ultimate, Kazuya's Moveset Inspector | 50 | **3,780 KB** | 0 |

Passing the pointer over a clip game's list downloads about 76 KB per row the learner never opens.

## 6. Memory

Each sequence ran in a fresh browser. Values are before → after.

| Sequence | JavaScript heap | Renderer process | GPU process | Other |
|---|---|---|---|---|
| Elden Ring: click 20 Greatsword weapons | 7.3 → 8.2 MB | 258 → 251 MB | 235 → 244 MB | 18 model files loaded. Flat, so not a problem at this scale. |
| Super Smash Bros. Ultimate: 10 Kazuya clips | 3.9 → 4.0 MB | 237 → 299 MB | 170 → **370 MB** | **171 MB of bitmaps decoded** for 10 clips |
| Hollow Knight: open `nkg.attack.firebats` (a 2,169 KB sheet) | 1.2 → 1.3 MB | 209 → 195 MB | 167 → **308 MB** | One sheet adds about 140 MB of GPU memory. |
| Five game switches: No Rest for the Wicked, Ninja Gaiden Black, Devil May Cry 3, Elden Ring, No Rest for the Wicked | 7.2 → 8.5 MB | 272 → 286 MB | 251 → **495 MB** | **6 WebGL contexts created**, none released; no browser warning yet |

The JavaScript heap stays small. The memory goes to decoded images and GPU resources, which the heap does not show.

## 7. Hosting and repository

| Measure | Value |
|---|---|
| Pages artifact | 553 MiB (580 MB) |
| Workflow run for PR #80 | about 70 s: checkout 16 s, upload 22 s, deploy 28 s. The run for PR #77 took 65 s to deploy. |
| Runs triggered | every push to `main`, including documentation-only pushes |
| Repository | 563 MiB in the pack plus 84 MiB of loose objects |
| Tracked files | 11,869 |

## What this means for the packages

| Package | Evidence from this baseline |
|---|---|
| WP-13 (Node host caching and compression) | **Weaker than assumed.** Pages already compresses and revalidates, and the Node host is not the public host. The real caching gap is Pages' 10-minute lifetime and per-deployment `ETag`s, which only fewer deployments (WP-14) or another media host (WP-23) can fix. |
| WP-14 (deploy only what the site serves) | **Confirmed.** 553 MiB per push; documentation-only pushes redeploy everything and reset every visitor's cache. |
| WP-15 (render on demand) | **Confirmed for the 3D viewer, strongly.** It renders at full rate in every idle state, hidden included. **Not needed for the sprite and clip viewers,** which already stop drawing when paused; scope 3 can shrink to an optional cleanup. |
| WP-16 (move switch cost) | **Partly confirmed.** Single steps are fast (about 170 ms at 1×). The problem is the queue while a key is held (4.0 s lag at 4×). The linear move lookup did not show up as long tasks. **Hover prefetch is confirmed:** 3.8 MB for 50 rows in a clip game. |
| WP-17 (re-render only what changed) | **Confirmed, strongly.** A 2 s slider drag blocks for 2.7 s at 1× and 37 s at 4×. |
| WP-18 (shorter first-load chain) | **Confirmed.** Throttled, the first 3D frame comes at 21.1 s, against a Largest Contentful Paint of 8.4 s. |
| WP-19 (bounded memory) | **Confirmed for clips, sprite sheets and game switches.** Not seen for 20 Elden Ring weapons. |
| WP-20 (Action Atlas posters) | **Confirmed.** 4.5 MB on the first screen, about 72 MB for the whole grid, 5.6 MB downloaded while typing a search. Throttled loads block for 3.1–3.6 s. |
| WP-21 (Trends summary data) | **Measured, less severe than the raw size suggested.** 512 KB of game data goes over the wire thanks to gzip, not 5.75 MB; Largest Contentful Paint is 6.6 s throttled. |
| WP-22 (Node host responsiveness) | Not measured: the Node host is not the production host. |
| WP-24 (fonts) | Fonts are 151 KB of each cold load. |

## Not measured

- **The Node host:** no production deployment was found.
- **A phone:** desktop comes first, per the project direction.
- **Lighthouse scores:** the same metrics were collected directly instead.
