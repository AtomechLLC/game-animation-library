# Before / after screenshots

Captured for the article on the UX changes. Shoot "after" with the same settings so the pairs line up.

- Viewport 1920×1080 at deviceScaleFactor 2 (PNG files are 3840 px wide), Chrome via Playwright
- Pages: `index.html` (built with `python build_page.py`) → `home-*`, `frame-data.html` (default Elden Ring view) → `frame-data-*`
- `*-viewport.png` is the first screen; `*-full.png` is the whole scrolled page
- Each page waits for network idle plus 5 s before capture

| Set | Date | Commit |
|---|---|---|
| `before/` | 2026-10-24 | e98edb6 |

## `pr-62/`

Per-feature pairs for PR #62. `before-*` is `main` at ca70ca1 (its page files over the same data), `after-*` is the branch at 7fd05da. Viewport 1600×900 at deviceScaleFactor 1, Chrome via Playwright, served by `serve_local.py`. GIFs are cropped screen recordings at 12 fps.
