# Melvor Idle 2 Guides

A local library of [skill leveling guides](guides/index.html), including material gathering, processing, assumptions, and auditable calculations. Use `$route` to create or revise a guide.

The [early money-making guide](guides/money-making/1-40/guide.html) covers Combat 1–30 and non-combat skills 1–40. It compares GP rates for selected methods, shows starter quest rewards, and includes an offline calculator for timing your own runs.

## Melvor Idle 2 research sources

Use pages and datasets that explicitly cover **Melvor Idle 2**, including on sites that cover both games. Exclude data from the original Melvor Idle and its expansions, even when items or skills share a name.

| Use | Reference |
| --- | --- |
| Identify the Steam release and read official announcements and patch notes. The developer's news site covers both Melvor games. | [Steam store](https://store.steampowered.com/app/3218350/), [Steam news for Melvor Idle 2](https://steamcommunity.com/app/3218350/allnews/), [Official Melvor Idle News](https://news.melvoridle.com/) |
| Check the public Steam branch's build ID and update date. | [SteamDB branches](https://steamdb.info/app/3218350/depots/#branches) |
| Look up items, recipes, equipment, monsters, quests, and the Mastery Guild in a community wiki that shows its Steam build. | [Melvor 2 Wiki](https://melvor2wiki.github.io/) |
| Trace base XP, inputs, outputs, step intervals, drop tables, and shop requirements by game ID. When a page omits its build, verify the values against the installed target build or a source that identifies it. | [Melvor DB](https://db.melvor.aevv.net/) |
| Check cumulative XP by level and find the source build for the XP table. | [Melvor2 XP table](https://melvor2.com/xp-table/) |
| Consult demo mechanics, tutorials, and training tables for historical comparison. Verify these values against the target build before using them for Early Access. | [Melvor Idle 2 Demo Database](https://melvoridle.wiki/melvor-idle-2), [Melvor2DB skill tables](https://melvor2db.com/skills/) |

For exact recipe values, prefer data from the installed target build when available. Check in-game behavior or official patch notes for mechanics that affect effective rates, such as failed attempts or skipped steps. Published base XP rates usually cover the listed action alone. The leveling guides also account for gathering and processing its inputs.

## Personalize a guide

After setting up the [character reader](tools/character_state/README.md), run this from the project root:

```powershell
.\update-guides.ps1 -Open
```

The command reads the latest local save and writes offline guides to `data/character/guides/`.

- `money-making-1-40.html` compares earning methods using your saved levels, bank, active tools, and supported modifiers. It shows missing requirements and compares each banked-material craft with selling its inputs. Its local GP/h calculator uses your measured session totals for combat, Thieving, or any other method.
- `fletching-1-50.html` uses your saved XP, banked materials, and supported modifiers to calculate the remaining stages and compare selected recipe alternatives.

Both guides identify the save timestamp and SHA-256, list sources for applied modifiers, and provide downloadable calculation data.

Use `-Save 'C:\path\character_save.sav'` to choose a character. Add `-Watch` to regenerate the guides each time the selected save changes while the command is running. Reload the pages to see the new results. In the Fletching guide, you can also enable periodic reloading in **Assumptions**. Press Ctrl+C in the terminal to stop watching.

For a feather gathering scenario, pass `-ChickenCycleSeconds 35` with your full Giant Chicken cycle time, including respawn and replenishing supplies. The default uses the guide's scenario. Estimates use average yields and cover a subset of game modifiers. Personal output stays in the Git-ignored character folder.

## Update or extend the money-making guide

Check the public Steam build and patch notes, then verify the new methods in the installed game. For each method, record the levels, tools or quest gates, ingredient chain, action timing, output chances, and sale prices. Add the verified action IDs to the relevant lists in [money_making.py](tools/character_state/money_making.py). Document unsupported mechanics or use the measured-session calculator. If the installed package changes, verify the model's formulas and update the reference build and package SHA-256 in [build_money_guide.py](tools/character_state/build_money_guide.py). Check the public guide text in [render_money_making.py](tools/character_state/render_money_making.py) and update the metadata date for the analysis.

The current artifact uses the non-combat cap in its range path, with the combat cap in the title and calculation data. To add a later range alongside it, give that range its own metadata, directory and build configuration. Keep the early comparison available to new players.

Regenerate the public files and library index, then test the personalized guide on a local save:

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/character_state/build_money_guide.py
.\.venv\Scripts\python.exe -X utf8 tools/character_state/build_money_guide.py --check
python -X utf8 .agents/skills/route/scripts/build_index.py
python -X utf8 .agents/skills/route/scripts/build_index.py --check
.\update-guides.ps1
```

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
