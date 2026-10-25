# WP-08: Funsmith club → Discord hub

**Status:** In progress (minimal) · **Priority:** P2 · **Depends on:** the Discord invite URL from Xelnath

## User task and intended outcome

*Contribute confidently* and the business goal. Visitors who want to discuss an example, ask a question or help
improve the library find the Discord easily, and the page feels like part of the Funsmith club community.

## Basis

**Stated goals** (Xelnath, 2026-10-24)
- "The Funsmith club is the brand for community collabs and does not need to match our color scheme."
- The Discord server is the hub for this page, "and vice versa".
- "Goal of this page is to get people to either join the discord or sign up for a waiting list for J's course."

**Observed problems**
- **The header link does not go to the Discord.** The "Funsmith club" button shows a Discord logo but links to
  `https://funsmith.club` (`template.html:169`, `frame-data.html:241`), so it is one extra step from the Discord.
- **There is no invitation where questions arise.** For example, nothing near a clip or a move says "discuss this
  in Discord".

**Proposal origin**
- Sungkuk: "it would make more sense to lead the 'Funsmith club' to Discord server directly."

## Proposed scope

1. Point the Funsmith club header link straight to the Discord invite, on both pages, with clear text such as
   "Join the Funsmith club on Discord".
2. Add one contextual invitation per surface: on an atlas entry ("Know a better example? Share it in Discord or
   submit a GIF") and in the Frame Data inspector ("Discuss this move").
3. Keep the page's visual identity as Funsmith club. Do not adopt the gamedesignskills.com colours.
4. Measure: add a UTM or ref parameter if the invite tooling supports it, so joins from the page can be counted.

## Out of scope

- A full visual rebrand.

## Open questions (for Xelnath)

- The permanent Discord invite URL, and whether a specific landing channel exists for library discussion.
- Should `funsmith.club` stay linked somewhere (for example the footer)?

## Done when

- Both page headers link to the Discord invite and open it in one click.
- At least one contextual invitation exists on each page.

## Evidence to capture

- Header before and after on both pages; the contextual invitation.

## Implementation record (as of 2026-10-25)

**Implemented**
- The Funsmith club header link opens in a new tab in all three apps (af19c74, PR #69; `frame-data.html:418`,
  `template.html:220`, `trends.html:207`).
- A Game Design Skills logo was added to the header (f0a96ca) and then reverted (2519264), which keeps the Funsmith
  identity of scope 3 intact.

**Not implemented**
- The link still points to `https://funsmith.club`, not a Discord invite (the invite URL is still needed).
- No "Discuss this move" link or Action Atlas Discord invitation.
- No referral tracking.
