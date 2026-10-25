# WP-22: Keep the Node host responsive

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-12

## User task it protects

*Contribute confidently.* Voting, proposing animations and uploading clips must feel responsive, and one
contributor's upload must not stall everyone else's page.

## Basis

**Observed problem**
- **The first page request after a restart hashes all clips while blocking the server.** `renderPage()`
  (`server.js:24-37`) filters blocked clips with `store.isBlockedGif`, which reaches `fileHash` in `lib/store.js`:
  a synchronous `readFileSync` plus SHA-256 of each local clip (852 files, about 162 MB). The cache is keyed by
  mtime, so it runs again after every restart, and after a deploy that changes mtimes. Every request waits
  meanwhile (estimated 0.3–3 seconds).
- **Every vote rewrites the whole database synchronously.** `save()` (`lib/store.js:36-40`) runs
  `JSON.stringify` of the whole database plus `writeFileSync` and `renameSync` on each change. It is called from
  voting in `lib/api.js` and about 15 places in `lib/admin.js`. With 10,000 votes that is about 2.3 MB per write.
  `state()` in `lib/api.js` loops over all votes on every page load.
- **Uploads are held in memory and written synchronously.** `readBody` (`lib/http.js:13-25`) buffers the whole
  request, `parseMultipart` copies it, `store.writeUpload` uses `writeFileSync`, and `isBlockedMedia` reads the file
  back and hashes it. A 25 MB video makes about three copies in memory.
- Smaller: the per-address rate-limit map in `store.rateOk` is never pruned; `renderPage()` rebuilds the blocklist
  sets and calls `statSync` twice on every page request.
- Good already: ffmpeg conversion runs asynchronously, one job at a time, at low priority (`lib/video.js`).

**Assumptions**
- Traffic is modest; the goal is no event-loop stalls, not throughput.

## Proposed scope

1. Store each clip's SHA-256 at build time (for example in the inlined data or a generated `gif-hashes.json`), or
   compute hashes asynchronously at startup before accepting traffic.
2. Batch database writes: mark dirty and write asynchronously at most once a second; keep vote tallies in memory.
3. Stream uploads to a temporary file, hashing while streaming; use `fs.promises` for writes.
4. Prune the rate-limit map periodically.

## Out of scope

- Replacing the JSON database with SQLite or another store (could follow if batching is not enough).
- Changing what contributors can do.

## Open questions

- Is a generated hash file acceptable as a new build output, or should hashing stay at server startup?
- Is losing up to one second of votes on a crash acceptable with batched writes?

## Metric

- Time of the first `GET /` after a restart: baseline from WP-12 → under 100 ms beyond normal rendering.
- Event-loop delay (p99, `perf_hooks.monitorEventLoopDelay`) during 100 votes and one 25 MB upload: baseline →
  under 20 ms.
- Server memory during two concurrent 25 MB uploads.

## Done when

- Voting, proposals, uploads and `/admin` actions behave as before, and `db.json` stays valid after a forced stop
  during voting.
- The measurements above are recorded against the WP-12 baseline.
