# Work packages (suggestions)

Every file in this folder is a **suggestion**. None is an adopted decision until Xelnath or Sungkuk marks it so.
The packages turn the product direction into scoped, verifiable pieces of work.

## Sources

- **[`CLAUDE.md`](../../CLAUDE.md):** product purpose, intended experience and UX principles.
- **[Elden Ring data inventory](../reports/elden-ring-data-inventory.md):** where the Elden Ring data lives,
  what is disconnected (§6), what is unreliable (§5.4) and the open questions (§7).
- **Discord thread between Sungkuk Park and Xelnath, 2026-10-24.** Points Xelnath stated:
  - gamedesignskills.com is the commercial brand. **Funsmith club** is the brand for community collaboration and
    does not need to match the commercial colour scheme.
  - The Discord server is the hub for this page, and the page is a hub for the Discord.
  - **The page's goal is to get people to join the Discord or sign up for the waiting list for Jacopo's course.**
    The course is the upcoming "Game feel and combat" course. Its outline has not been submitted yet.
  - Ideally the page works both as a community space (for example, uploading GIFs) and as a way to bring people to
    the course.
- **Sungkuk's first focus**, from the same thread: improve the Frame Data viewer, because it is hard to find a
  specific animation there.

As `CLAUDE.md` asks, each package keeps four things apart: **stated goals** (Xelnath), **observed problems**
(evidence from code or data), **assumptions**, and **proposed solutions**.

## Status values

`Suggestion` → `Adopted` → `In progress` → `Done`. A package can also be `Parked` or `Rejected`, with a reason.

## Packages

| # | Package | User task | Priority | Depends on | Status |
|---|---|---|---|---|---|
| 01 | [Find a move by what it is](wp-01-frame-data-findability.md) | Find relevant examples | P1, first focus | none | Suggestion |
| 02 | [Recognise moves visually](wp-02-visual-move-browsing.md) | Find, observe | P1 | 01 (soft) | Suggestion |
| 03 | [Elden Ring viewport and inspector](wp-03-er-viewport-inspector.md) | Observe deliberately, compare | P1 | 06 | Suggestion |
| 04 | [Join moves and atlas entries](wp-04-move-atlas-join.md) | Find, compare | P2 | none | Suggestion |
| 05 | [Teaching links to an exact moment](wp-05-teaching-links.md) | Use examples in teaching | P2 | 03, 04 | Suggestion |
| 06 | [Hide or relabel unreliable fields](wp-06-unreliable-fields.md) | Observe, teach (accuracy) | P1, small | none | Suggestion |
| 07 | [Browsable Common animations](wp-07-common-animations.md) | Find, observe | P3 | 01, 03 | Suggestion |
| 08 | [Funsmith club → Discord hub](wp-08-funsmith-discord-hub.md) | Contribute; business goal | P2 | invite URL | Suggestion |
| 09 | [Course waiting-list call to action](wp-09-course-waitlist.md) | Business goal (course discovery) | P2, blocked | course outline, waitlist URL | Suggestion |
| 10 | [Approachable contribution flow](wp-10-contribution-flow.md) | Contribute confidently | P3 | 08 | Suggestion |
| 11 | [Before/after evidence and article](wp-11-before-after-article.md) | Resource for others | Ongoing | each package | Suggestion |

The current focus is the Elden Ring viewport and inspector. Packages 01 to 06 fall inside that scope. Packages 07
to 10 matter to the page's goal but should not widen the active task unless adopted.

## Evidence

Screenshots are not stored in the repository. The "before" state is commit `e98edb6`; [package 11](wp-11-before-after-article.md) has the capture settings.
Each package lists the "after" shots it needs so [package 11](wp-11-before-after-article.md) can pair them.

## Template

```
# WP-NN: Title
Status · Priority · Depends on
## User task and intended outcome
## Basis (stated goal / observed problem / assumptions)
## Proposed scope
## Out of scope
## Open questions
## Done when
## Evidence to capture
```
