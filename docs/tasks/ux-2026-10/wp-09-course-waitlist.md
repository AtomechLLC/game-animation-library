# WP-09: Course waiting-list call to action

**Status:** Suggestion (blocked; related link on Trends only) · **Priority:** P2 · **Depends on:** the course outline, a waitlist URL or form, and copy
approval (all from Xelnath / Jacopo)

## User task and intended outcome

Business goal: course discovery. Visitors who are interested in game feel find out about Jacopo's upcoming
"Game feel and combat" course and can join its waiting list. Learners are not interrupted while studying.

## Basis

**Stated goals** (Xelnath, 2026-10-24)
- The page's goal is to get people to join the Discord *or sign up for a waiting list for J's course*.
- The course is "Game feel and combat". Jacopo still needs to submit the course outline.
- The page should be both a community space and a way to bring people to the course.

**Observed problem**
- The page has no mention of the course or the waiting list (no match in `template.html` or `frame-data.html`).

**Assumptions to test**
- A call to action placed where a learner is already thinking about game feel converts better and feels less
  intrusive than a banner. Example places: next to timing explanations, the phase legend, or after comparing two
  moves.

## Proposed scope

1. One persistent, low-key entry point (header or footer) on both pages: "Game feel and combat course: join the
   waiting list".
2. One contextual placement in the Frame Data inspector or legend that connects what the learner sees (anticipation,
   commitment) to the course.
3. A simple waitlist destination. Use an external form if Xelnath has one; otherwise propose a minimal form backed
   by `server.js` (needs a decision on data handling).

## Out of scope

- Writing course content or marketing copy beyond a short line, without approval.
- Pop-ups or modals.

## Open questions (for Xelnath)

- The waitlist URL or form owner, and what data it may collect.
- Approved course name and one-line description. Please also confirm the spelling: the thread says "Jacobo",
  `CLAUDE.md` says "Jacopo".
- Should the call to action mention gamedesignskills.com (the commercial brand) or stay under Funsmith club?

## Done when

- Both pages link to the waiting list from one persistent place and from one contextual place.
- The link opens the approved destination.

## Evidence to capture

- Both placements, on the home page and the Frame Data page.

## Implementation record (as of 2026-10-25)

**Related work**
- Trends has a "Further reading" block linking to the gamedesignskills.com "Polishing Game Feel Bootcamp" and a
  combat design guide (`trends.html:222-228`; 2c372ef PR #65, 75ba310 PR #66, 6d05eb2 PR #67).

**Not implemented:** the waiting-list call to action itself. It is still blocked on the course outline and a
waitlist URL or form. Nothing course-related appears in the Action Atlas or Move Explorer.
