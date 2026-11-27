# Melvor Idle 2 Guides

A local library of [skill leveling guides](guides/index.html), including material gathering, processing, assumptions, and auditable calculations. Use `$route` to create or revise a guide.

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
