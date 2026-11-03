# WP-38: One local server

**Status:** Suggestion · **Priority:** P2 · **Depends on:** none

## User task it protects

*Contribute confidently*, and the content direction of replacing weak examples. The owner marks a weak clip once, in
one place, and the follow-up (a Claude search or the `/admin` review) always finds that mark.

## Basis

**Observed problem**
- Two local servers serve the same three apps (see the
  [README table](../../../README.md#running-a-local-server)):
  - `python serve_local.py` on port 8765 adds **✕ Bad GIF** and **✕ Needs better GIFs** to Action Atlas. It
    saves them to `marks.json` in the repo.
  - `npm start` (`server.js`) on port 3000 adds votes, suggestions and proposals. A signed-in admin also gets
    **⚑ Mark for replacement**, saved as `needs` in `~/library-data/db.json` (`lib/store.js`, `lib/api.js`
    `action=need`).
- So "this clip needs replacing" is recorded in two stores, by two buttons, under two names. Neither server reads
  the other's marks.
- Each server keeps its own list of served paths. The code-sharing round already had to note that new folders need
  routes in both (`server.js` and `serve_local.py` only serve listed paths).
- `template.html` carries a `local` mode (`CFG.local`, `CFG.marks`) that exists only for `serve_local.py`. Its error
  message names that server ("Is serve_local.py running?").

**Assumptions**
- The split comes from the PHP backend (`046f77b`), which was hard to run locally. Since `32bec09`, `server.js` runs
  locally with `npm start` and no `.env`, so that reason no longer holds.
- The Claude workflow ("search for better GIFs for my marks") needs the marks readable from the repo or the
  workstation, not only from a server's `db.json`.
- The owner is the only person who uses `serve_local.py`.

## Proposed scope

1. Make `server.js` the one local server. When it runs locally (on `127.0.0.1` with no `ADMIN_PASSWORD_HASH`, or
   behind an explicit setting such as `LOCAL_REVIEW=1`), the owner can mark entries and GIFs without signing in.
2. Use one mark feature: the existing **⚑ Mark for replacement** (`needs`). Get the marks to the Claude workflow
   either by writing `marks.json` as they change, or by an **Export marks** link on `/admin` like the existing
   **Export blocklist**. Choosing between these is the first open question.
3. Remove the `local` mode from `template.html` and `build_page.py`. Turn `serve_local.py` and `serve_local.bat`
   into thin launchers for `npm start`, or remove them.
4. Update `README.md` (replace the two-server table), `CLAUDE.md` (Hosting line), `DEPLOY-XCLOUD.md` ("Running it
   locally") and the README section on the marks workflow.

## Out of scope

- Any change to how votes, suggestions, proposals or the `/admin` review behave on the deployed site.
- The contents of `marks.json`, `library.json` or any other data file.
- GitHub Pages, which stays a static read-only copy.

## Open questions

- Which store holds marks: `db.json` with an export to `marks.json`, or `marks.json` written directly when local?
- Should marking without a password be possible at all, or only after a local sign-in?
- Keep a Python launcher for an owner without Node.js, or require Node 20+?
- Does the Claude prompt "search for better GIFs for my marks" need to change?

## Metric

- Local servers: 2 → 1.
- Stores for "needs replacement" marks: 2 → 1.
- Lists of served paths to keep in sync: 2 → 1.

## Done when

- One command runs Action Atlas, Move Explorer and Trends locally, with marking.
- A clip marked locally reaches the Claude replacement workflow, checked end to end with one mark.
- On a server with `.env` set, votes, suggestions, proposals, `/admin` sign-in and **⚑ Mark for replacement**
  behave as before.
- `template.html` has no `local` mode and no `serve_local.py` message, and the docs listed above are updated.
