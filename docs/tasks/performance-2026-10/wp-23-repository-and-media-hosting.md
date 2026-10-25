# WP-23: Repository size and a home for media

**Status:** Suggestion · **Priority:** P2 (needs a decision) · **Depends on:** WP-14

## User task it protects

*Contribute confidently.* Contributors and future maintainers need to clone and work on the repository without a
multi-gigabyte download, and the collection needs room to grow with better clips and more games.

## Basis

**Observed problem**
- The repository pack is **563 MB**, plus 82 MB of loose objects; 11,851 tracked files; no Git LFS
  (`.gitattributes` only marks media as binary).
- Packed size by folder: `frame-data/clips` 211 MB, `gifs` 174 MB (973 versions for 849 current files),
  `frame-data/models` 91 MB, `frame-data/sprites` 85 MB, and `docs/screenshots` 65 MB.
- `docs/screenshots` was deleted from the working tree (e5410cb, 58f90ac) but is still in history; its largest file
  is a 16 MB `home-full.png`.
- Every replaced clip stays in history, so the repository grows with each curation pass, which is exactly the work
  `CLAUDE.md` asks for ("replace weak or misleading examples").
- GitHub Pages limits a site to 1 GB (see WP-14).

**Assumptions**
- Git LFS is a poor fit: the Pages workflow checks out on every push and would use up the LFS bandwidth quota.

## Proposed scope

This package is a decision record, not an implementation. Compare and recommend one of:

1. **Keep media in the repository**, run `git gc`, and accept the growth; rely on WP-14 for the Pages limit.
2. **Rewrite history** to drop `docs/screenshots` (`git filter-repo`), recovering about 65 MB. Needs every
   contributor to re-clone.
3. **Move media to object storage or a content delivery network** (for example Cloudflare R2) with the pages
   loading media from there, and keep only manifests in git.
4. **A separate media repository** published as its own Pages site.

For each: cost, contributor workflow (importers, `serve_local.py`, the Node host), effect on clone time and on the
1 GB limit, and migration steps.

## Out of scope

- Doing the migration. That becomes its own package once a direction is chosen.

## Open questions

- Who decides, and what hosting budget exists? This needs Xelnath.
- Does the Node host need to serve the same media, or can both hosts point to one media origin?

## Metric

- Fresh clone size and time; `git count-objects -vH` (WP-12).

## Done when

- A short decision note in this file records the chosen option and the reasons, adopted by Xelnath or Sungkuk.
