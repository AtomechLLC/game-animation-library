# WP-34: One page shell stylesheet

**Status:** Suggestion · **Priority:** P1 · **Depends on:** none

## User task it protects

*Use examples in teaching.* An instructor moves between Action Atlas, Move Explorer and Trends during a class. The
apps should look like one library: the same colours, type, header and focus rings, in light and dark.

## Basis

**Observed problem**
- The top of each app's `<style>` is copied: `template.html:15–70`, `frame-data.html:15–79`, `trends.html:16–76`.
  About 60 lines are identical in all three
  ([report, section 4](../../reports/duplicated-app-code.md#4-page-shell-styles-in-all-three-apps)).
- Colour tokens live in three blocks per app: light (`:root`), dark by system preference
  (`@media (prefers-color-scheme: dark)`) and dark by attribute (`:root[data-theme="dark"]`). One shared colour is
  written in up to nine places. #84 had to add `--focus` to six of them.
- Also copied: fonts, base rules (`body`, `button`, `:focus-visible`, `.wrap`, `[hidden]`), the sticky header, brand,
  the Funsmith club link and the app switcher styles (`.apps`, `.approw` and their phone rule).

**Assumptions**
- The shared tokens and rules are identical today, so moving them changes nothing on screen. This is checked line by
  line before moving, not assumed.
- App-specific tokens are deliberate and stay in their app: Move Explorer's frame phase colours (`--f-*`) and cancel
  colours (`--cx-*`), Trends' chart colours (`trends.html:81–83`).

## Proposed scope

1. `shared/shell.css` with the shared tokens (all three blocks), fonts and base rules, header, brand, club link and
   app switcher styles.
2. Each app links it before `shared/ruler.css` and keeps only its own tokens and rules.
3. Keep the dark mode structure as it is (preference plus attribute), so nothing about theme switching changes.
4. Note in `README.md` that shared colours and the shell are changed in `shared/shell.css`.

## Out of scope

- Changing any colour, size or font.
- The filter rail and sheet styles (WP-36) and the app switcher markup (WP-35).

## Open questions

- Should the shared tokens be split from the shell rules (`shared/tokens.css` and `shared/shell.css`), so a future
  page that only wants the palette can take it alone?

## Metric

- Places one shared colour is written: up to 9 → 3 (the three blocks in `shared/shell.css`).
- Identical shell lines across the apps: about 60 per app → 0.

## Done when

- Each app's own `<style>` holds no rule or token that another app also defines identically.
- Screenshots of the three apps' headers, in light, dark by preference and dark by attribute, match before and after.
- `shared/shell.css` is served by `server.js` and `serve_local.py` (the `/shared/` route) and by GitHub Pages.
