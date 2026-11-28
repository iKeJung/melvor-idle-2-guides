# Melvor Idle 2 Guides

A local library of [skill leveling guides](guides/index.html), including material gathering, processing, assumptions, and auditable calculations. Use `$route` to create or revise a guide.

## Melvor Idle 2 research sources

Use pages and datasets that explicitly cover **Melvor Idle 2**, including on sites that cover both games. Exclude data from the original Melvor Idle and its expansions, even when items or skills share a name.

| Use | Reference |
| --- | --- |
| Identify the Steam release and read official announcements and patch notes. The developer's news site covers both Melvor games. | [Steam store](https://store.steampowered.com/app/3218350/), [Steam news for Melvor Idle 2](https://steamcommunity.com/app/3218350/allnews/), [Official Melvor Idle News](https://news.melvoridle.com/) |
| Check the public Steam branch's build ID and update date. | [SteamDB branches](https://steamdb.info/app/3218350/depots/#branches) |
| Look up items, recipes, equipment, monsters, quests, and the Mastery Guild in a community wiki that shows its Steam build. | [Melvor 2 Wiki](https://melvor2wiki.github.io/) |
| Trace base XP, inputs, outputs, step intervals, drop tables, and shop requirements by game ID. Check the build separately when a page omits it. | [Melvor DB](https://db.melvor.aevv.net/) |
| Check cumulative XP by level and find the source build for the XP table. | [Melvor2 XP table](https://melvor2.com/xp-table/) |
| Consult demo mechanics, tutorials, and training tables for historical comparison. Verify these values against the target build before using them for Early Access. | [Melvor Idle 2 Demo Database](https://melvoridle.wiki/melvor-idle-2), [Melvor2DB skill tables](https://melvor2db.com/skills/) |

For exact recipe values, prefer data from the installed target build when available. Check in-game behavior or official patch notes for mechanics that affect effective rates, such as failed attempts or skipped steps. Published base XP rates usually cover the listed action alone. The leveling guides also account for gathering and processing its inputs.

## Personalize a guide

After setting up the [character reader](tools/character_state/README.md), run this from the project root:

```powershell
.\update-guides.ps1 -Open
```

The command reads the latest local save and generates an offline guide in `data/character/guides/`. Fletching 1–50 uses your saved XP, banked materials, and supported modifiers to calculate the remaining stages and compare selected recipe alternatives. The page shows the save time and sources for applied modifiers and offers a download of its calculations as JSON.

Use `-Save 'C:\path\character_save.sav'` to choose a character. Add `-Watch` to regenerate the guide each time the selected save changes while the command is running. Reload the page, or enable periodic reloading in its **Assumptions** section. Press Ctrl+C in the terminal to stop watching.

For a feather gathering scenario, pass `-ChickenCycleSeconds 35` with your full Giant Chicken cycle time, including respawn and replenishing supplies. The default uses the guide's scenario. Estimates use average yields and cover a subset of game modifiers. Personal output stays in the Git-ignored character folder.

## Inspect character data

To read your character's latest local save without controlling the game, run in PowerShell:

```powershell
.\extract-character.ps1
```

The report is written to `data/character/report.html`, alongside `state.json`, `agents.json`, and `bonus.json`. Personal outputs and extracted game data stay outside Git. See [setup, coverage, and limitations](tools/character_state/README.md).

Agents can query a specific stat with an automatic refresh:

```powershell
.\query-character.ps1 -Skill Smithing -Stat SkipStepChance
```

The JSON response includes units, the identified subtotal, sources, and limitations. For batch queries, use `data/character/agents.json` according to the [format contract](tools/character_state/AGENT-FORMAT.md).

All repository content is maintained in English, and commits follow Conventional Commits. See [AGENTS.md](AGENTS.md).

## English migration

The English interface replaces the previous Portuguese commands, paths, and JSON keys. Character snapshots and the agent query contract now use **schema version 2**; regenerate snapshots with `extract-character.ps1` before using `-Cache`. Guide metadata and the generated catalog also use version 2 for English status values (`reference`, `validated`, `partial`). Calculation files retain their existing version because their fields and numeric meaning are unchanged.

The library now lives in `guides/`, the character tools in `tools/character_state/`, and the skill in `.agents/skills/route/`. Use `-Skill`, `-Component`, `-Type`, and `-Output` with PowerShell, or `--skill`, `--component`, `--type`, and `--output` with Python. Older personal snapshots remain ignored and are not automatically migrated. Saves and game files are unchanged.
