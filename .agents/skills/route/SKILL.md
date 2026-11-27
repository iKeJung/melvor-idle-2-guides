---
name: route
description: "Research Melvor Idle 2 skill leveling routes, account for the material chain, and generate local reference guides by skill and level range. Use when creating or revising a leveling guide in this project."
---

# Route

Create a researched guide and an HTML reference artifact in this project's library. Include ingredient gathering time as well as final crafting. Write all repository content and guide output in English, preserving official English game item names. Follow the root AGENTS.md language and Conventional Commits rules.

## Input

- Identify the skill and starting/target levels from the request and current context.
- If any required detail is missing, ask in one message: **"Which skill do you want to analyze, and from which level to which level?"** Ask only for missing fields. Do not repeat answered questions.
- Wait for required details before selecting a route. Meanwhile, investigate sources and the existing library if useful.
- Validate integer levels, a starting level below the target, and a range supported by the researched version. Do not assume every skill or version shares the same cap.
- By default, minimize total time to the target level, starting at the exact beginning of the stated level, without stock and with auxiliary skills already at the required levels. Use base modifiers as a reference. Sufficient auxiliary levels do not imply unlocked equipment, ranks, quests, or upgrades.
- Incorporate stock, current XP, equipment, bonuses, or other objectives supplied by the user. Ask about other conditions only when essential; otherwise record assumptions and conditional scenarios.

## Research and calculation

1. Confirm the game and version. This project's default is **Melvor Idle 2**; do not mix in recipes or bonuses from the first Melvor Idle. Consult current web sources, prioritizing extracted game data, mechanics documentation, and databases that identify builds. Record dates, URLs, and known builds; explain relevant discrepancies.
2. Compare options unlocked within the range and their dependencies: gathering, processing, intermediates, and final actions. Account for batch yields, probabilities, failures, guaranteed success limits, respawn, and consumables. Do not treat one hit or substep interval as a complete cycle.
3. Calculate **effective XP/h = 3,600 × target skill XP across the chain ÷ total chain seconds**. Include intermediate XP when it trains the target skill. Auxiliary skill XP is a separate benefit. Avoid counting time, shared products, or already earned XP twice.
4. Examine relevant alternatives: shops, combat, Thieving, and parallel production. For purchases, include the time to generate currency or inputs when needed. Distinguish level requirements from guild/quest unlocks. For Farming/Ranching, distinguish active time from waiting that actually blocks the route. Do not assign a full independent cost to each coproduct of one action.
5. When a rate depends on the character and cannot be measured, state an explicit assumption and compare thresholds or scenarios. Do not present invented combat speed as an observed rate. Do not claim a universally optimal route when only the base scenario was analyzed.
6. Derive stage quantities from the verified XP curve, rounding to whole batches and carrying XP and leftovers between stages. Validate arithmetic with executed scripts or calculations. Separate time spent unlocking upgrades from time saved by them.

## Artifact and storage

Use this structure relative to the project root:

```text
guides/
  index.html                          # generated offline index
  catalog.json                        # generated catalog; do not edit manually
  <skill-slug>/
    <start>-<end>/
      guide.html                      # complete, standalone, printable guide
      metadata.json                   # record used to build the index
      calculations.json               # auditable assumptions, inputs, and results
```

- Use the English skill name as a lowercase, hyphenated slug: `fletching`, `woodcutting`, `firemaking`. Do not create different aliases for one skill.
- Before writing, inspect the catalog and range directory. If the skill/range already exists, revise that guide and preserve useful material; do not create dated copies or `final-2` variants. A different range gets another directory.
- `guide.html` must open through `file://`, without a server, remote libraries, or `fetch`. Include internal navigation, readable mobile layout, responsive tables, and print styling. Use the existing Fletching guide as a visual reference without copying its recipes, assumptions, or conclusion to another skill.
- Make the content practical: recommendation and conditions, route by level range, materials, stage/total times, alternatives, at least one worked chain calculation, bonus/stock adjustments, and sources linked to relevant facts. Distinguish observed, published, and calculated information.
- `calculations.json` must be a JSON object with `guide_id` matching the metadata `id`, units, assumptions, recipe inputs, and per-stage results. Record unverified rates as scenarios with their origin. Choose an organization appropriate for the skill; the HTML and JSON numbers must agree.
- Create `metadata.json` using this format (replace values with the new analysis):

```json
{
  "schema_version": 2,
  "id": "fletching-1-50",
  "game": "Melvor Idle 2",
  "skill": "Fletching",
  "slug": "fletching",
  "level_start": 1,
  "level_end": 50,
  "title": "Fletching from level 1 to 50",
  "summary": "A route including gathering and crafting every material.",
  "updated_on": "2026-11-27",
  "status": "reference",
  "artifact": "guide.html",
  "calculations": "calculations.json",
  "tags": ["gathering included", "base rates"]
}
```

`status`: `reference` for a route calculated with assumptions; `validated` when also checked on the described character/configuration; `partial` when relevant unavailable data remains and is explicitly identified in the guide. The date is the actual analysis creation/revision date, not a simple index rebuild date. Version 2 uses English status values; older metadata must be migrated before rebuilding.

## Required completion

1. Check HTML, internal links, relative files, and consistency of materials/times. Do not replace research with a template filled with unverified numbers.
2. Run from the project root:

   ```powershell
   python -X utf8 .agents/skills/route/scripts/build_index.py
   python -X utf8 .agents/skills/route/scripts/build_index.py --check
   ```

   The script validates records before generating `guides/catalog.json` and `guides/index.html`. `--check` verifies integrity and synchronization without writing. Fix failures before delivery.
3. Confirm the index includes the guide and all paths point to existing files.
4. Deliver absolute links to **the final guide and the library index**. Briefly state the assumption with the largest effect on the recommendation. Delivering the file is part of the task; do not finish with chat research alone.
