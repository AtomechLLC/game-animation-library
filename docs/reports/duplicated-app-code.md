# Code duplicated across the apps

Where the three apps carry their own copies of the same code, how far those copies have already drifted, and in
what order they could be brought together.

- **Snapshot:** `main` at commit `7310cb2` (2026-10-25), which includes the shared ruler from #84.
- **Scope:** the three apps — Action Atlas (`template.html`), Move Explorer (`frame-data.html`) and Trends
  (`trends.html`) — and the scripts they load (`shared/`, `frame-data/*.js`). Section 9 lists what was not examined.
- **Prompted by:** #76 scoped Left/Right to the focused zone on the Move Explorer ruler. Action Atlas and Trends never
  received it, because each app had its own copy of the ruler. #84 moved the ruler into `shared/ruler.css` and
  `shared/ruler.js`. This report looks for other places where the same thing can happen.
- **Nature:** findings and proposals. Nothing here has been changed; each consolidation would be its own pull request.

## 1. Summary

The ruler was not an isolated case. Five more groups of code are copied between apps, ranked here by how likely a
change to one copy is to miss the others:

1. **The preview controls** (play, step a frame, scrub, keyboard, link state) are copied into all three preview
   modules: the 3D preview, the 2D sprite preview and the hitbox clip preview. This is the closest match to the ruler
   case: a change to how the arrow keys step frames has to be made three times, or one game type behaves differently.
2. **The page shell styles** (colour tokens, fonts, header, brand, app switcher) are copied into all three apps. One
   colour lives in up to nine places.
3. **The app switcher markup** (about 4,500 characters with three inline icons) is copied into all three apps,
   including a hard-coded game count.
4. **The filter rail and detail sheet** are shared by Action Atlas and Move Explorer in spirit but copied in fact,
   and several of their rules have already drifted apart.
5. **Small script helpers** (`$`, `esc`, hash state, `lastActive`) are copied, and `lastActive` already gives a
   different answer in Trends than in Move Explorer.

Already shared, for contrast: `shared/ruler.css` and `shared/ruler.js` (#84), and in Move Explorer
`frame-data/speed.js` (the speed menu every preview uses), `navigation3d.js` and `renderstats.js`.

## 2. Method

Three measurements, run as throwaway scripts over the files in scope:

- **Identical lines:** every trimmed line of 25 characters or more that appears in more than one file (inline icon
  paths and embedded images excluded). Runs of such lines show copied blocks.
- **Same selector, different rules:** for each CSS selector defined in more than one app, whether the declarations
  match. A mismatch is either a deliberate difference or drift.
- **Same name, compared bodies:** top-level functions and constants defined in more than one file, with a text
  similarity ratio between their bodies.

Limits: copies that were renamed, reordered or reformatted are counted only where they still share long identical
lines. The similarity ratio says how alike two bodies are, not whether they behave the same; section 7 reads the one
case where that matters.

Counts across the three apps: 117 lines identical in at least two apps, of which 58 appear in all three, 44 only in
Action Atlas and Move Explorer, and 14 only in Move Explorer and Trends.

## 3. Preview controls in the three preview modules

**Where:** `frame-data/viewer3d.js`, `frame-data/sprites2d.js` and `frame-data/clipviewer.js`. Move Explorer docks
whichever one suits the game (3D models, sprite sheets or recorded hitbox clips).

**What is copied:** 31 lines are identical in all three, and 6 more in the 3D and sprite previews. Together they are
the whole transport around the picture:

| Part | viewer3d.js | sprites2d.js | clipviewer.js |
|---|---|---|---|
| Play, ±1 frame buttons and scrub bar markup | 86 | 33 | 13 |
| Key help line (`.v3d-keys`) | 92 | 39 | 19 |
| `setPlaying` | 255 | 87 | 66 |
| `go` (move to a frame) | 256 | 78 | 58 |
| `onKey` (Space, `,` `.`, arrows, Ctrl and Shift jumps) | 263 | 94 | 72 |
| Link state: `toggles`, `view`, `setView` | 381–384 | 130–133 | 115–118 |

**Drift so far:** small. The three `onKey` handlers differ by one line: the 3D preview leaves Numpad `.` to its camera
("Fit to view"). The 3D and sprite previews share `once`, `json` and the start of `createViewer` as well.

**Risk:** this is the same shape as the ruler. When arrow keys were added for stepping frames (`7ca2e72`), the
same lines had to be written into all three modules in one commit; that time none was missed. The next change to
frame stepping, the key help line or the link format has to be repeated the same way. If one copy is missed, a student stepping through a Street Fighter III hitbox clip
gets different keys from one stepping through an Elden Ring 3D move — the comparison the library is built for
becomes harder.

**Precedent:** `frame-data/speed.js` already does this for the speed menu: one module, imported by all three.

## 4. Page shell styles in all three apps

**Where:** the top of each app's `<style>`: `template.html:15–70`, `frame-data.html:15–79`, `trends.html:16–76`.

**What is copied:** about 60 identical lines per app:

- **Colour tokens**, in three blocks per app: light (`:root`), dark by system preference
  (`@media (prefers-color-scheme: dark)`) and dark by attribute (`:root[data-theme="dark"]`). A shared colour such as
  `--focus` therefore has to be written in nine places; #84 added it to six (Action Atlas and Trends), and Move
  Explorer already had its three.
- Fonts, base rules (`body`, `button`, `:focus-visible`, `.wrap`, `[hidden]`), the sticky header, brand, the Funsmith
  club link and the app switcher styles (`.apps`, `.approw` and the phone rule).

**Deliberate differences, to keep:** Move Explorer adds frame phase colours (`--f-*`) and cancel colours (`--cx-*`);
Trends adds chart colours (`trends.html:81–83`). These are app-specific and stay in the app.

**Risk:** a palette change, a new token or an accessibility fix to focus rings is easy to make in one app and miss in
another. Mismatched colours between apps also weaken the feeling of one library.

## 5. App switcher markup

**Where:** `template.html:204`, `frame-data.html:407`, `trends.html:191`.

**What is copied:** the whole `<nav class="apps">`, 4,554 characters in each app, identical except for which link
carries `aria-current="page"`. It includes the three app icons as inline SVG and the subtitle text.

**Drift risk already built in:** the Move Explorer subtitle says "Step through moves frame by frame · 7 games" in all
three copies. Adding a game means editing three files, or the switcher shows different counts depending on which
app it is in. The count could come from `frame-data/games.json` instead.

## 6. Filter rail and detail sheet in Action Atlas and Move Explorer

**Where:** Move Explorer's style opens with "Same shell as template.html (sticky timeline header, filter rail,
slide-over sheet)". The two apps share 44 identical lines that Trends does not have: the filter rail (`aside`,
`.flist`, `.fitem`), chips, active-filter buttons, status line, scrim, detail sheet, footer and phone rules.

**Drift so far:** several rules with the same selector already differ:

| Rule | Action Atlas | Move Explorer |
|---|---|---|
| `.sheet` width | 560 px (`template.html:110`) | 600 px (`frame-data.html:175`) |
| `.meta` label column | 110 px (`template.html:114`) | 130 px (`frame-data.html:185`) |
| `.status p` | muted, `max-width:65ch` (`template.html:86`) | muted only (`frame-data.html:99`) |
| `closeSheet()` | also clears the link hash (`template.html:426`) | leaves the hash (`frame-data.html:816`) |

Some of these are likely deliberate (Move Explorer's sheet holds frame tables), but nothing records which. The
`closeSheet` difference is behaviour, not layout: closing a sheet in Action Atlas changes the shareable link, in Move
Explorer it does not.

**Risk:** improvements to the filter rail or the sheet (keyboard handling, focus return, phone layout) land in one
app. For instructors who move between Action Atlas and Move Explorer in class, the two sheets behave slightly
differently.

## 7. Small script helpers

| Helper | Where | State |
|---|---|---|
| `$` (query one element) | `template.html:372`, `frame-data.html:452`, `trends.html:223` | identical |
| `esc` (escape text for HTML) | `template.html:373`, `frame-data.html:453`, `trends.html:224` | identical |
| `writeHash`, `fromHash` (link state) | `frame-data.html:822, 841`, `trends.html:527, 529` | same pattern, different fields |
| `lastActive` (last active frame of a move) | `frame-data.html:493`, `trends.html:288` | **diverged** |

`$` and `esc` are one line each; copying them is cheap and they rarely change. `esc` matters more, since every app
uses it to keep data out of the markup.

`lastActive` is the meaningful one. Both apps read the same per-game frame data, but the copies answer differently
for a move with no active frames: Move Explorer returns `0`, Trends returns `null` and also tolerates a missing
`active` list. Trends then skips such moves where Move Explorer would treat them as ending at frame 0. Today this may
be harmless, but it is the kind of quiet difference that makes the two apps disagree about the same move. Trends
recomputes other frame data meanings from the same files too, so any rule about what the data means (for example,
which frames count as active) is safest defined once.

## 8. Suggested order to consolidate

Proposals only, highest value first. Each would be a separate pull request following the pattern of #84. They are
written up as work packages WP-33 to WP-37 in [`docs/tasks/code-sharing-2026-10/`](../tasks/code-sharing-2026-10/README.md).

1. **Preview controls** into one module beside `speed.js` (for example `frame-data/transport.js`): markup, keys,
   `go` and `setPlaying` wiring, link state. Each preview keeps only its drawing and its own extra keys (the 3D
   preview's Numpad `.`). Highest value because these controls are what students use to observe moves.
2. **Page shell styles** into `shared/shell.css`: the three token blocks and the header, brand and switcher rules.
   App-specific tokens stay in each app.
3. **App switcher** rendered from one place (a small script in `shared/`, which can also read the game count from
   `frame-data/games.json`), leaving each app to mark itself current.
4. **Filter rail and sheet** for Action Atlas and Move Explorer: first record which differences in section 6 are
   deliberate, then share the rest. Decide whether closing a sheet should clear the link in both apps.
5. **Helpers:** share `$` and `esc`; define frame data meanings such as `lastActive` once for Move Explorer and Trends.

Constraints that apply to every step, learned from #84:

- Action Atlas is built: `build_page.py` turns `template.html` into `index.html`. Shared files must be loaded by
  relative path, not inlined at build time, so that one copy serves all three apps.
- `server.js` and `serve_local.py` only serve listed paths; a new shared folder needs a route in both (as `/shared/`
  got in #84).
- Shared files are cached for an hour; each page links them with `?v=` and the number is bumped on change.

## 9. Not examined

- Python tools (`tools/`, importers, `build_index.py`, `merge.py`), and the server code in `server.js` and `lib/`.
- `tools/er_gifs/render.html` and `render.js`: checked only for the app shell; they do not use the app tokens or
  header.
- Duplication inside a single app.
