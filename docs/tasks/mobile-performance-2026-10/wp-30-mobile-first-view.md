# WP-30: A lighter first view on phones

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-25, WP-18 (soft)

## User task it protects

*Find relevant examples.* A student who opens Move Explorer from a link on a phone should see the move list quickly,
without a multi-megabyte download before they have chosen anything.

## Basis

**Observed problem**
- **The default view loads a 3.7 MB model.** Move Explorer opens on Elden Ring with the first class shown as an
  example in the 3D viewer (`frame-data.html:786-797`), so the armor model
  `frame-data/models/elden-ring/armor-haligtree-knight.glb` loads on every first visit:
  - 3,681,568 bytes, about 2.38 MB after gzip (if the host compresses it at all);
  - no Draco or meshopt geometry compression; only normals are quantized; positions are 32-bit floats;
  - one 1024 × 1024 PNG texture is 1.36 MB, 37% of the file; the other textures are JPEGs;
  - 36,487 vertices, 23 materials (about 23 draw calls) and 150 bones.
  It is about 70% of the default view's compressed transfer.
- **The chain is long on a slow connection.** The model loads only after the game JSON is parsed. With Lighthouse
  mobile throttling on desktop, the first 3D frame came at **21.1 s** against a Largest Contentful Paint of 8.4 s
  ([baseline](../../reports/performance-2026-10/baseline.md), section 1).
- **No device or connection signal is used.** Nothing reads `navigator.connection.saveData`, `effectiveType` or
  `deviceMemory`; a phone on cellular gets the same automatic 3D preview as a desktop.
- **Renderer settings are desktop defaults.** `new THREE.WebGLRenderer({antialias: true, alpha: true})` with the
  pixel ratio capped at 2 (`frame-data/viewer3d.js:99-100`). On a phone the stage is small, but iPads wider than
  820 px get the desktop layout, about 1400 × 880 device pixels with multisampling.

**Assumptions**
- On a phone the move list is the first thing a learner needs; the example preview can wait for a tap.
- WP-18 shortens the chain for everyone; this package decides what a phone loads at all.

## Proposed scope

1. On small screens with a coarse pointer, or when Save-Data is on, show the example viewer's stage with a "Show
   preview" button instead of loading the model automatically. Once the learner opens a move, load as today.
2. On those devices, cap the 3D pixel ratio at 1.5 and pass `powerPreference: 'low-power'`; keep desktop settings
   unchanged.
3. Measure the effect of compressing the default model (meshopt or Draco geometry, a JPEG or KTX2 texture instead of
   the PNG) on a copy, so the media decision below has numbers.

## Out of scope

- Re-exporting or replacing committed models (see open questions).
- Changing the desktop default view.

## Open questions

- Should the Elden Ring exporter compress models (meshopt or Draco) and textures (KTX2 or JPEG)? That changes
  generated media and the loader setup (a decoder script), and needs its own decision.
- Is a tap-to-load preview acceptable on phones, or should the default example move be one with a lighter model?

## Metric

- Emulated phone, WP-25 cold load of Move Explorer, throttled: bytes transferred and time to the move list being
  usable; baseline → without the model's 2.4 MB until the learner asks for a preview.
- Time from tapping "Show preview" (or a move) to the first 3D frame: measured, so the trade-off is visible.
- Desktop cold load: unchanged.

## Done when

- A phone's first visit to Move Explorer does not download a 3D model until the learner asks for one, and desktop
  behaviour is unchanged.
