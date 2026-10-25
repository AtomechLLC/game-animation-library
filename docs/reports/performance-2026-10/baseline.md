# Performance baseline, 2026-10-25

The measurements for [WP-12](../../tasks/performance-2026-10/wp-12-performance-baseline.md). Later performance
packages (WP-13 to WP-24) compare against these numbers, measured the same way.

- **Raw data:** [`baseline-2026-10-25.json`](baseline-2026-10-25.json)
- **Script:** [`tools/perf/baseline.mjs`](../../../tools/perf/baseline.mjs)
- **Site measured:** the live GitHub Pages site, https://atomechllc.github.io/game-animation-library/, deployed from
  commit `77bae24` (run 40197741443).

## How it was measured

**Host.** GitHub Pages is the production host: every push to `main` deploys there (`.github/workflows/static.yml`),
and the repository variable `LIBRARY_API_URL` is not set, so the public pages do not use the Node host. Node host
measurements from the WP-12 scope were therefore left out.

**Setup**

| Item | Value |
|---|---|
| Browser | Chrome 155.0.8059.85, headless, 1440 × 900 window, device scale 1 |
| Machine | Intel Core Ultra 9 275HX, 64 GB memory, Windows 11 |
| WebGL | ANGLE on the integrated Intel Graphics (Direct3D 11) |
| Unthrottled | this machine on its own connection |
| Throttled | Lighthouse's default mobile throttling: 150 ms round trip, 1.6 Mbit/s down, 750 kbit/s up, CPU 4× slower |
| Profiles | a fresh browser profile per scenario, so the first load of each scenario is a cold cache |

**Repeat it**

```
node tools/perf/baseline.mjs                       # every scenario, about 7 minutes
node tools/perf/baseline.mjs --only load,idle      # some scenarios
node tools/perf/baseline.mjs --base http://localhost:8000/ --out <file>   # another copy of the site
```

The script loads instrumentation into each page before the page's own scripts run. It records:
- long tasks;
- paint and event timings;
- WebGL draw calls, and how many animation frames contained a draw;
- decoded `ImageBitmap` bytes;
- `history.replaceState` calls;
- WebGL contexts created.

It also wraps page functions (`renderAll`, `renderTable`, `preview`, `stepMove`, `dock`, the viewer's `show`, and
the Action Atlas's `render`) to time them. **The apps' code is not changed.**

**How to read the numbers**

- **Long tasks:** main-thread tasks over 50 ms.
- **Blocking time:** the part of each long task over 50 ms, summed. On a page load it counts only after First
  Contentful Paint, as Total Blocking Time does.
- **Slowest event:** the longest input event duration. It stands in for Interaction to Next Paint.
- **Settled times for asynchronous functions** (`show`, `preview`, `dock`) run until the returned promise resolves,
  so they include downloads and waiting in a queue.
- **Headless Chrome is not limited to the display's refresh rate.** It ran animation frames at about 165 per
  second. On a 60 Hz monitor the same loop runs 60 times a second. The comparison between states (playing, paused,
  folded) is what matters.
- **Process memory** is the operating system's private memory per Chrome process type.
- **Decoded bitmaps** count every `ImageBitmap` created, not those still alive.

## 1. Page loads

Cold means an empty cache. Repeat means navigating away and back within Pages' 10-minute cache lifetime.

### Unthrottled

| App | First Contentful Paint | Largest Contentful Paint | First 3D frame | Blocking time | Requests | Transferred |
|---|---|---|---|---|---|---|
| Action Atlas, cold | 1.08 s | 1.08 s | — | 59 ms | 29 | 4,514 KB (images 4,178 KB) |
| Action Atlas, repeat | 0.27 s | 0.43 s | — | 52 ms | 29 | 0 KB |
| Move Explorer, cold | 1.17 s | 1.66 s | 2.00 s | 217 ms | 82 | 3,158 KB |
| Move Explorer, repeat | 0.08 s | 0.38 s | 0.47 s | 58 ms | 82 | 0 KB |
| Trends, cold | 0.90 s | 1.85 s | — | 92 ms | 17 | 872 KB |
| Trends, repeat | 0.07 s | 0.31 s | — | 93 ms | 13 | 0 KB |

### Throttled (school Wi-Fi stand-in)

| App | First Contentful Paint | Largest Contentful Paint | First 3D frame | Blocking time | Longest task | Transferred |
|---|---|---|---|---|---|---|
| Action Atlas, cold | 1.72 s | 1.72 s | — | 3,461 ms | 2,094 ms | 4,515 KB |
| Action Atlas, repeat | 0.58 s | 0.58 s | — | 2,553 ms | 998 ms | 0 KB |
| Move Explorer, cold | 1.74 s | 8.06 s | **20.65 s** | 2,442 ms | 992 ms | 3,158 KB |
| Move Explorer, repeat | 0.42 s | 2.51 s | 2.97 s | 2,065 ms | 1,018 ms | 0 KB |
| Trends, cold | 1.46 s | 6.07 s | — | 1,099 ms | 913 ms | 873 KB |
| Trends, repeat | 0.36 s | 2.14 s | — | 1,433 ms | 1,173 ms | 0 KB |

**Move Explorer's cold transfer by type** (unthrottled):

| Type | KB |
|---|---|
| Fetched data and models | 2,506 |
| Scripts | 296 |
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
| First screen | 29 requests, 4,514 KB |
| Scrolling the whole grid (321 cards, 17 s) | another 297 requests, **67,541 KB** |
| Total for the whole grid | about 72 MB |
| Main thread while scrolling | no long tasks |
| Idle at the bottom of the grid | no WebGL; main thread 23 ms busy per second; GPU process 160 ms of CPU per second (the animated thumbnails on screen) |

## 3. Interactions

| Interaction | CPU | Long tasks | Blocking time | Slowest event | Other |
|---|---|---|---|---|---|
| Action Atlas: type "heavy atta" (10 characters, 120 ms apart) | 1× | 3 (longest 85 ms) | 60 ms | 112 ms | `render` ×10, 75 ms in total; **5,656 KB downloaded** while typing |
| | 4× | 7 (longest 584 ms) | 1,357 ms | 704 ms | `render` ×10, 502 ms |
| Move Explorer: drag the startup slider for 2 s | 1× | **58** (longest 155 ms) | **2,648 ms** | 16 ms | `renderAll` ×58 (1,101 ms), 58 `replaceState` calls |
| | 4× | 65 (longest 1,108 ms) | **38,802 ms** | 96 ms | `renderAll` ×58 (8,015 ms); the page stays blocked for about 40 s after a 2 s drag |
| Move Explorer: pick the Greatsword class | 1× | 0 | 0 ms | 80 ms | `renderAll` 24 ms; viewer shows the move 129 ms after the call |
| | 4× | 6 (longest 284 ms) | 395 ms | 408 ms | `renderAll` 137 ms |
| Move Explorer: one Down step, key to first frame of the next move (6 steps) | 1× | — | — | — | 127–145 ms |
| | 4× | — | — | — | 140–235 ms |
| Move Explorer: hold Down for 2 s (61 key events) | 1× | 0 | 0 ms | 24 ms | 61 previews; slowest `show` settles 316 ms after its key |
| | 4× | 16 (longest 82 ms) | 107 ms | 112 ms | slowest `show` settles **3.9 s** after its key: the previews queue up |

**What the numbers say**

- **The startup slider is the worst interaction measured.** `renderAll` itself is only 20% of the long-task time at
  1×. The rest is style and layout after the `innerHTML` rewrites, plus the viewer reloading the example move on
  each tick (`dock`, settling in up to 554 ms at 1× and 2.8 s at 4×).
- **Holding Down does not block input,** but at 4× the move shown lags the key by up to 3.9 s, because every step
  starts its own `show`.
- **`replaceState` ran once per step** (61 in 2 s). It stayed under Chrome's throttling threshold in this test, and
  no console warning appeared.
- **The class view keeps 92 rows in the hidden `#table`** next to 81 rows in the Moveset Inspector (3,869 DOM nodes
  in total).

## 4. Idle cost of the 3D viewer (Greatsword class, 5 s each)

| State | WebGL frames per second | Draw calls per second | Main thread busy per second | Renderer + GPU process CPU per second |
|---|---|---|---|---|
| Playing | 165 | 6,158 | 160 ms | 288 + 367 ms |
| **Paused** | 173 | 6,401 | 109 ms | 217 + 383 ms |
| **Folded ("Hide") and paused** | 167 | 6,194 | 84 ms | 99 + 110 ms |
| **Example viewer scrolled off screen, paused** | 164 | 6,068 | 115 ms | 175 + 111 ms |

A paused, folded or off-screen viewer renders exactly as often as a playing one, about 37 draw calls per frame. With
the display's frame-rate limit, that would be 60 frames and about 2,200 draw calls per second on a 60 Hz monitor.

## 5. Memory

Each sequence ran in a fresh browser. Values are before → after.

| Sequence | JavaScript heap | Renderer process | GPU process | Other |
|---|---|---|---|---|
| Elden Ring: click 20 Greatsword weapons | 7.4 → 8.4 MB | 255 → 254 MB | 236 → 249 MB | 16 model files loaded; flat, so not a problem at this scale |
| Super Smash Bros. Ultimate: 10 Kazuya clips | 3.9 → 4.0 MB | 228 → 297 MB | 175 → **369 MB** | **171 MB of bitmaps decoded** for 10 clips |
| Hollow Knight: open `nkg.attack.firebats` (2,169 KB sheet) | 1.2 → 1.3 MB | 207 → 189 MB | 167 → **309 MB** | one sheet adds about 140 MB of GPU memory |
| Five game switches (No Rest for the Wicked, Ninja Gaiden Black, Devil May Cry 3, Elden Ring, No Rest for the Wicked) | 7.3 → 8.6 MB | 212 → 324 MB | 240 → **503 MB** | **6 WebGL contexts created**, none released; no browser warning yet |

The JavaScript heap stays small. The memory goes to decoded images and GPU resources, which the heap does not show.

## 6. Hosting and repository

| Measure | Value |
|---|---|
| Pages artifact | 553 MiB (580 MB) |
| Workflow run | about 1 min 45 s: checkout 14 s, upload 22 s, deploy 65 s |
| Runs triggered | every push to `main`, including documentation-only pushes |
| Repository pack | 563 MiB in pack, plus 82 MiB loose objects |
| Tracked files | 11,866 |

## What this means for the packages

| Package | Evidence from this baseline |
|---|---|
| WP-13 (Node host caching and compression) | **Weaker than assumed.** Pages already compresses and revalidates, and the Node host is not the public host. The real caching gap is Pages' 10-minute lifetime and per-deployment `ETag`s, which only fewer deployments (WP-14) or another media host (WP-23) can fix. |
| WP-14 (deploy only what the site serves) | Confirmed: 553 MiB per push; documentation-only pushes redeploy everything and reset every visitor's cache. |
| WP-15 (render on demand) | **Confirmed and strong:** paused, folded and off-screen viewers render at full rate. |
| WP-16 (move switch cost) | **Partly confirmed:** single steps are fast (about 130 ms at 1×). The problem is the queue while a key is held (3.9 s lag at 4×). The linear move lookup did not show up as long tasks. |
| WP-17 (re-render only what changed) | **Confirmed and strong:** a 2 s slider drag blocks for 2.6 s at 1× and 39 s at 4×. |
| WP-18 (shorter first-load chain) | **Confirmed:** throttled first 3D frame at 20.7 s, versus Largest Contentful Paint at 8.1 s. |
| WP-19 (bounded memory) | **Confirmed for clips, sprite sheets and game switches.** Not seen for 20 Elden Ring weapons. |
| WP-20 (Action Atlas posters) | **Confirmed:** 4.5 MB first screen, about 72 MB for the whole grid, 5.6 MB downloaded while typing a search. Throttled loads block for 2.5–3.5 s. |
| WP-21 (Trends summary data) | Measured: 513 KB of game data on the wire, Largest Contentful Paint 6.1 s throttled. Less severe than the 5.75 MB raw size suggested, thanks to gzip. |
| WP-22 (Node host responsiveness) | Not measured: the Node host is not the production host. |
| WP-24 (fonts) | Fonts are 151 KB of each cold load. |

## Not measured

- **The Node host:** no production deployment found.
- **A phone:** desktop first, per the project direction.
- **Lighthouse scores:** the same metrics were collected directly instead.
- **Hover prefetch over the move table:** the script does not sweep the pointer over rows yet.
