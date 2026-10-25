# WP-36: One filter rail and detail sheet

**Status:** Suggestion · **Priority:** P2 · **Depends on:** WP-34 (soft)

## User task it protects

*Find relevant examples* and *Use examples in teaching.* Action Atlas and Move Explorer both filter a list with a
side rail and open details in a slide-over sheet. A student or instructor who uses both should find them working the
same way, including what happens to the shared link.

## Basis

**Observed problem**
- Move Explorer's style opens with "Same shell as template.html (sticky timeline header, filter rail, slide-over
  sheet)". In practice the two apps share 44 identical lines that Trends does not have: the filter rail (`aside`,
  `.flist`, `.fitem`), chips, active-filter buttons, status line, scrim, sheet, footer and phone rules
  ([report, section 6](../../reports/duplicated-app-code.md#6-filter-rail-and-detail-sheet-in-action-atlas-and-move-explorer)).
- Several rules with the same selector have already drifted:

| Rule | Action Atlas | Move Explorer |
|---|---|---|
| `.sheet` width | 560 px (`template.html:110`) | 600 px (`frame-data.html:175`) |
| `.meta` label column | 110 px (`template.html:114`) | 130 px (`frame-data.html:185`) |
| `.status p` | muted, `max-width:65ch` (`template.html:86`) | muted only (`frame-data.html:99`) |
| `closeSheet()` | also clears the link (`template.html:426`) | leaves the link (`frame-data.html:816`) |

- The `closeSheet` difference is behaviour: closing a sheet in Action Atlas changes the shareable link, in Move
  Explorer it does not.

**Assumptions**
- Some differences are deliberate (Move Explorer's sheet holds frame tables and may need the extra width), but
  nothing records which. This package does not guess; it asks first.

## Proposed scope

1. Decide, for each row of the table above, whether the difference is deliberate. Record the answer as a comment
   where the rule stays app-specific.
2. Decide whether closing a sheet should clear the link in both apps, in neither, or stay different.
3. Move the agreed-identical rail, chip, status, scrim and sheet rules into a shared stylesheet (part of
   `shared/shell.css` from WP-34, or `shared/rail-sheet.css`). Each app keeps its deliberate differences.
4. Share the sheet's open and close behaviour (scrim, Escape, link handling, focus) once the decision in step 2 is
   made.

## Out of scope

- Redesigning the rail or the sheet.
- The sheet's content, which is specific to each app.
- Trends, which has neither.

## Open questions

- Which of the four differences above are deliberate? Needs Sungkuk or Xelnath.
- Should closing the sheet clear the link? Clearing it keeps a copied link from reopening a sheet the visitor closed;
  keeping it makes the back button return to the open sheet.
- Should focus return to the row that opened the sheet, in both apps, as part of this package?

## Metric

- Identical rail and sheet lines in the two apps: 44 → 0.
- Unrecorded differences between the two apps' rail and sheet: 4 → 0 (each is shared or commented as deliberate).

## Done when

- The open questions have answers recorded in this file.
- The rail and sheet look and behave as decided in both apps, in light and dark, at desktop width and below 820 px.
- Opening, closing (button, scrim, Escape) and sharing a link to a sheet work in both apps.
