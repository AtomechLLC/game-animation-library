# WP-13: Compress and revalidate on the Node host

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-12

## User task it protects

*Find relevant examples* and *use examples in teaching*: returning to the library, for example at the start of each
class, should not download the same megabytes again.

## Basis

**Observed problem**
- **No compression.** `serveFile` (`server.js:41-48`) writes `Content-Type`, `Content-Length` and `Cache-Control`,
  then streams the raw file. `send` (`lib/http.js:84-87`) sends the Action Atlas page the same way. Nothing is
  gzip- or brotli-compressed.
- **No validators.** No `ETag` or `Last-Modified` header is sent and `If-None-Match` is never checked, so a
  revalidation is always a full `200`.
- **Every visit downloads everything again:**
  - The Action Atlas page is `no-cache` (`server.js:56`): 837 KB raw, 182 KB gzipped.
  - Move Explorer and Trends pages are `max-age=0` (`server.js:62, 64`).
  - All frame data JSON is `max-age=0` (`server.js:66`): `elden-ring.json` 1.55 MB, `super-smash-bros-ultimate.json`
    2.56 MB, plus `models.json`, `moves/*.json`, `icons.json`. JSON usually gzips to 10–15%.
  - Models, clips, sprites and icons get `max-age=3600` with no validator, so after an hour they download in full.
- **No range requests.** Community MP4s play in `<video>` when ffmpeg is absent (`template.html:318`); Safari needs
  `Range` support to play them.
- `DEPLOY-XCLOUD.md` does not say whether the Nginx in front compresses responses. Its default `gzip_types` covers
  only `text/html`.

**Assumptions**
- GitHub Pages already compresses and sends `ETag`s, so this package matters only for the Node host.
- Files under `frame-data/` change only when an importer runs, so mtime plus size is a safe validator.

## Proposed scope

1. `ETag` (from mtime and size, or a hash of the rendered Action Atlas page) on every static and page response,
   answering `If-None-Match` with `304`.
2. Compression for HTML and JSON: serve precompressed `.br`/`.gz` siblings when present, otherwise `zlib` on the
   fly with a small in-memory cache for the Action Atlas page. Do not compress WebP, GLB or the binary animation
   files.
3. Longer cache lifetimes for media that only changes on import (models, animation files, clips, sprites, icons),
   still revalidated by `ETag`.
4. `Accept-Ranges` and `206` responses for video.
5. Note the Nginx compression setting in `DEPLOY-XCLOUD.md`.

## Out of scope

- A content delivery network (see WP-23).
- Fingerprinted file names for frame data (could follow if `ETag` revalidation is not enough).

## Open questions

- Is compression better done in Node or in the xCloud Nginx? If Nginx, this package shrinks to `ETag` + range +
  documentation.

## Metric

- Repeat visit to Move Explorer (Elden Ring): bytes transferred, baseline about 1.6 MB of JSON → target under 20 KB
  (all `304`).
- Cold visit: JSON bytes on the wire → about 15% of today's.
- Measured with DevTools Network on the Node host, cache enabled, as in WP-12.

## Done when

- A repeat visit to each of the three apps answers its HTML and JSON with `304`.
- `Content-Encoding: br` or `gzip` appears on HTML and JSON responses.
- An MP4 community clip plays in Safari from the Node host.
