# WP-07: Browsable Common animations

**Status:** Suggestion · **Priority:** P3 · **Depends on:** WP-01, WP-03

## User task and intended outcome

*Find relevant examples* and *observe deliberately* beyond attacks. Locomotion, rolls, hit reactions, deaths,
gestures and interactions can be studied frame by frame like attacks.

## Basis

**Observed problems** (inventory §3.4, §3.6, §5.2)
- **245 Common animations are invisible to learners.** They are already exported (`moves/common.json`,
  `anim/*.bin`) and labelled in `tools/er_gifs/common_anims.json` (30 `want` groups such as roll, death, jump,
  knockdown, guard, gesture). They are used only to render atlas GIFs and are not visible in the Frame Data tab.
- **Most Elden Ring atlas entries are not attacks.** They are locomotion, reactions, defense and interaction, and
  these animations are their source.

**Assumption to test**
- Learners value studying non-attack animations in the viewer, not only as GIFs.

## Proposed scope

1. Add a "Common" section, or a pseudo class, to the Elden Ring Frame Data view. Group it by `want`, using the
   `common_anims.json` labels.
2. Open these in the same viewport. They have no hit or timing data, so show only frame count and labels, without
   empty number fields.
3. Make the labels searchable (WP-01).

## Out of scope

- Adding timing data for Common animations.

## Open questions

- Is this in the current Elden Ring scope, or a follow-up once WP-01 to WP-03 land?

## Done when

- A user can find and play "roll", "ladder climb" or "knockdown" in the viewer by search or by group.

## Evidence to capture

- The Common group list and one Common animation in the viewport.
