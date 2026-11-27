# Melvor Idle 2 Guides

A local library of [skill leveling guides](guides/index.html), including material gathering, processing, assumptions, and auditable calculations. Use `$route` to create or revise a guide.

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
