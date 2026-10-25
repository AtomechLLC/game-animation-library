# WP-35: One app switcher

**Status:** In progress · **Priority:** P2 · **Depends on:** WP-34 (soft)

## Progress

- **Done:** the switcher, the Funsmith club link and the title are written once by `shared/appbar.js` and styled by
  `shared/appbar.css`; each app marks itself current with `data-app`. This also fixed a phone problem: each app had
  its own phone rules for this row (Trends had none), so on a phone the row was 87 px tall in Action Atlas, 99 px in
  Move Explorer and 189 px in Trends, and changed shape on every switch. It now has one phone layout (the club as
  its Discord icon alone, the title on one line, name-only app buttons), the same 87 px in all three. Desktop is
  unchanged. A cross-document view transition keeps the bar still while the app below changes, where supported.
- **Open:** the game count is still written into the subtitle ("· 7 games"), not read from `frame-data/games.json`.

## User task it protects

*Find relevant examples.* The app switcher tells a visitor what each app is for and how much it holds. It should say
the same thing in every app, and stay correct when a game is added.

## Basis

**Observed problem**
- The whole `<nav class="apps">` is copied into each app: `template.html:204`, `frame-data.html:407`,
  `trends.html:191`. Each copy is 4,554 characters, identical except for which link carries `aria-current="page"`
  ([report, section 5](../../reports/duplicated-app-code.md#5-app-switcher-markup)).
- It includes the three app icons as inline SVG and the subtitle text.
- The Move Explorer subtitle, "Step through moves frame by frame · 7 games", is hard-coded in all three copies.
  Adding an eighth game means editing three files, or the switcher shows different counts in different apps.

**Assumptions**
- The game count can come from `frame-data/games.json`, which Move Explorer and Trends already load and which is
  small.

## Proposed scope

1. The switcher markup lives once in `shared/` (a small script that writes it, or an HTML fragment it inserts).
2. Each app keeps a placeholder `<nav>` and marks itself current.
3. The game count is read from `frame-data/games.json`; until it arrives, the subtitle shows no count rather than a
   wrong one.
4. The switcher stays readable without the script where possible (open question below).

## Out of scope

- Changing the switcher's design, icons, colours or text other than the count.
- Adding or removing apps.

## Open questions

- Should the markup stay in each page and only the count become live, so the switcher never depends on a script? That
  keeps the copies but removes the part that goes stale.
- In Action Atlas, `build_page.py` could insert the shared markup at build time instead. That works for Action Atlas
  only; the other two apps are static files.

## Metric

- Copies of the switcher markup: 3 → 1.
- Places to edit when a game is added: 3 → 0.

## Done when

- The three apps show the same switcher, with the current app marked, in light and dark.
- Adding a game to `frame-data/games.json` updates the count in all three apps with no other edit.
- Keyboard focus and screen reader names of the switcher links are unchanged.
