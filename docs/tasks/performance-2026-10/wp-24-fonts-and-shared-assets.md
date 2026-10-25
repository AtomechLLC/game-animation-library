# WP-24: Fonts and shared header assets

**Status:** Suggestion · **Priority:** P3 · **Depends on:** WP-12

## User task it protects

*Find relevant examples.* Text should appear on the first paint in all three apps, and moving between apps should
reuse what the browser already has.

## Basis

**Observed problem**
- Each app (`template.html:10-11`, `trends.html:10-11`, `frame-data.html:10-11`) loads three Google Fonts families
  with eight weights through a stylesheet that blocks rendering.
- The pages preconnect to `fonts.googleapis.com` but not to `fonts.gstatic.com` (with `crossorigin`), where the font
  files come from. `display=swap` is set (good).
- Each page inlines the same base64 favicon (about 2.8 KB) and header icons (about 4.6 KB of SVG), so they are
  downloaded again with every page instead of cached once. About 7 KB per page; small.

**Assumptions**
- Some of the eight weights are unused; the audit did not check each one.

## Proposed scope

1. Add `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` in all three apps.
2. Remove font weights that no style uses.
3. Optionally move the favicon and header icons into one shared, cacheable file.

## Out of scope

- Changing typefaces or the visual design.
- Self-hosting fonts (could follow if the preconnect is not enough).

## Open questions

- None known.

## Metric

- First Contentful Paint and font-load completion on a throttled cold load of each app (WP-12 setup).

## Done when

- All three apps look the same as before, with the measured paint times recorded against the baseline.
