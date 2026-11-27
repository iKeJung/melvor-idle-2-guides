# Melvor Idle 2 Guides

This project maintains a library of skill leveling routes. To create or revise a skill guide, read and follow the [route skill](.agents/skills/route/SKILL.md).

## Language and commits

- Write all new or updated repository content in **English**, including documentation, guides, skill instructions, code comments, identifiers, filenames, CLI messages, generated reports, and JSON field names. Preserve official game IDs, proper names, source quotations, and third-party license notices where required.
- Use **Conventional Commits** for every commit: `<type>(<optional scope>): <description>`. Write the description and any body in English. Examples: `refactor(character): translate the query interface to English` and `docs: clarify guide assumptions`. Use `!` or a `BREAKING CHANGE:` footer when introducing an incompatible public interface.
- Keep paths, examples, schemas, tests, and generated artifacts consistent when changing names. Regenerate derived files rather than editing them by hand.

## Character queries by agents

When the user asks about **their character** (level, XP, bonuses, equipment, or upgrades), query local saves by command. This workflow does not require UI control, screenshots, manual exports, or uploading saves to websites.

Prefer a focused query from the project root:

```powershell
.\query-character.ps1 -Skill Smithing -Stat SkipStepChance
```

- The query **refreshes the save snapshot by default** and returns JSON on stdout. Check the exit code and `status`; after an error, do not treat an earlier output as current. `-Cache` explicitly queries an existing snapshot without refreshing it; report its date and this limitation.
- Without `-Stat`, the query returns the skill's level, XP, and all identified modifiers. Preserve English game IDs such as `Smithing`, `SkipStepChance`, `DoublingChance`, and `PercentXPGained`. Matching is case insensitive. For an ambiguous stat, add `-Component Action -Type ArtisanAction`.
- For equipment/toolbelts and masteries, refresh the snapshot and inspect `state.json` at `skills.<Skill>.tools` / `mastery`; combat equipment and inventory are in `decoded_state.json`.
- Confirm `snapshot.character`, `snapshot.character_id`, the save timestamp, and `snapshot.save_age_seconds`. The default selects the most recent `.sav`; use `-Save 'path\character_save.sav'` to select a specific character.
- Read `modifier.confirmed_general.value` together with `unit`. With `percentage_fraction`, `0.06 = 6%`; the `percentage` field already contains `6`. `ms` means milliseconds. Do not convert `game_value` without checking its mechanics.
- **The value is a subtotal of identified modifiers, not a final chance or rate.** `complete: false` and `final_value: null` are intentional. Contextual, uncertain, and global groups are excluded from the subtotal. Apply conditional modifiers only when the action context matches and the condition can be verified; do not add global groups or sources to the subtotal again.
- `status: unidentified`, `modifier: null`, or `confirmed_general: null` means unknown, **never zero**. A numeric subtotal of `0` differs from absence. Always inspect `coverage`, `contextual`, `uncertain`, `other_and_global_bonuses`, and `sources` before drawing conclusions.
- Prioritize identified values and their sources in the answer; mention limitations that affect the conclusion. For personalized calculations, record the snapshot SHA-256 and the modifiers used as assumptions. Do not replace a generic route's assumptions with personal data without a request or context that calls for it.

The generated `data/character/agents.json` file is the batch query interface, indexed by `skills.<Skill>.modifiers.<Component>.<Type>.<Stat>`.
Run `.\extract-character.ps1` to refresh all files.
See [AGENT-FORMAT.md](tools/character_state/AGENT-FORMAT.md) for the format, examples, and limitations, and the [tool README](tools/character_state/README.md) for setup and interpretation.
Personal saves and snapshots must remain ignored by Git, including outputs created before the English migration.

## Project skill

- **route** — Research a skill and level range, calculate the material chain, and deliver a reference artifact. Entry point: [.agents/skills/route/SKILL.md](.agents/skills/route/SKILL.md).

## Workflow for each guide

1. Obtain the skill and starting/target levels; ask only for missing details.
2. Research Melvor Idle 2 and record sources, version, and assumptions. Assume auxiliary skills already meet the required levels, and include the time to gather and process materials.
3. Save `guide.html`, `metadata.json`, and `calculations.json` in `guides/<skill>/<start>-<end>/`.
4. Update the existing guide when the skill and range match. Use a different directory for another range. Do not scatter new guides in the root.
5. Run the index builder and its `--check` mode as described in the skill. `guides/index.html` and `guides/catalog.json` are generated from metadata.
6. Deliver links to the guide and library. The task is complete only when the artifact is saved and included in the index.

Examples: `Use $route` or `Create a Woodcutting route from level 10 to 50`. In the first case, ask for the skill and range; in the second, start researching.
