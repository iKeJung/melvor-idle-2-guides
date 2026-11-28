# Character state

Read the latest local **Melvor Idle 2 Steam/Windows** autosave without opening windows or controlling the UI. The reader was tested with save v32 and Steam build 26886380. It also accepts v31; other save versions are rejected.

Set up the environment once from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools\character_state\requirements.txt
```

Then refresh by command:

```powershell
.\extract-character.ps1
```

The script finds the game in Steam libraries and reads the most recent `.sav` in `%APPDATA%\Games By Malcs\Melvor Idle 2`. With multiple characters, select the file explicitly:

```powershell
.\extract-character.ps1 -Save 'C:\path\character_save.sav'
```

It also accepts `-Exe 'F:\SteamLibrary\steamapps\common\Melvor Idle 2\Melvor2.exe'` and `-Output 'F:\Melvor-idle-2\data\character'`. An absolute `.ps1` path works from another working directory. The script does not install mods or write to saves, the game directory, or AppData. After setup, it runs without network access.

Outputs in `data/character/`:

- `report.html`: levels, XP, general skill bonuses, and source details.
- `state.json`: consolidated state for queries and route calculations (schema v2).
- `agents.json`: compact skill/component/type/stat index, with deduplicated sources and an explicit distinction between subtotals and final values (schema v2).
- `bonus.json`: modifiers by source and Bonfire/rare event state.
- `decoded_state.json`: intermediate data including toolbelts, purchases, pets, Astrology, masteries, equipment, and inventory.

These files are local and ignored by Git, as are `.cache/` (proprietary game data) and `.venv/`. The script does not upload saves. It is not a continuous monitor: run it again to refresh. The save timestamp and SHA-256 identify the snapshot. Concurrent writes are retried, and decoding uses a temporary copy. On failure, the last successful output remains; always check its timestamp.

## Personalized money-making

Run `.\update-guides.ps1 -Open` from the project root. Select a character with `-Save` or add `-Watch` to regenerate when that save changes. The money-making page and its audit JSON are stored in `data/character/guides/`. The estimate uses the selected save's levels, active supported modifiers, available cash for modeled shop inputs, and unlocked bank stacks. GP/h for repeatable artisan methods includes gathering and processing. Banked-material jobs show added value over selling the inputs. Combat uses base loot values and your measured session totals. Thieving estimates include stuns and common loot. Use the session calculator to include food and the time spent replacing picks.

## Agent queries

```powershell
.\query-character.ps1 -Skill Smithing -Stat SkipStepChance
```

Queries refresh the snapshot by default and return the requested JSON with units, sources, timestamps, character identity, and coverage. Without `-Stat`, they return all identified modifiers for the skill. `-Cache` uses an existing snapshot and marks that no refresh occurred. Failures never fall back to cache automatically. See the [v2 contract and examples](AGENT-FORMAT.md); agent usage rules are in the root [AGENTS.md](../../AGENTS.md).

## Interpreting bonuses

`skills.<name>.general_bonuses` sums only confirmed modifiers without context. Each contribution is listed in `sources`. `value` retains the game unit: `0.03` with `unit: percentage` is displayed as `+3%`; `-100` with `unit: ms` means `-100 ms`. The report does not calculate final chances or apply action floors, caps, or multipliers. The compact agent interface names the fractional percentage unit `percentage_fraction`.

`contextual_bonuses` preserves recipe/category/item, conditions, and scaling. For example, the Flax basket modifies only the Flax Bush recipe. Do not apply these modifiers to the whole skill. `uncertain_bonuses` includes masteries whose rank the reader cannot determine; these are excluded from confirmed totals. Other components and global groups remain in `other_and_global_bonuses`, without automatic expansion into each skill.

Coverage includes toolbelts and equipped potions, active equipment, sets meeting their piece thresholds, purchases, pets, permanent Astrology nodes, masteries, Hunting Journal, Fishing bait, enabled Bonfire with time remaining, and active RareEvents.

Limitations: Ranching animals/enclosures, internal Astrology events, Thieving distractions/heists, Agility techniques, environmental conditions, and combat effects/passives/stances/prayers are not yet totaled. The snapshot does not advance offline progress. **An empty list does not mean the character has no bonuses from these sources.** Partial coverage is declared in JSON and in the report.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools\character_state -p 'test_*.py' -v
```

Synthetic tests cover v32 bank tab icons, v31 compatibility, XP boundaries, invalid regions, two-handed equipment, contextual/uncertain/global separation, set piece thresholds, Bonfire activation/duration, and query failures without an implicit cache fallback. Previous real-save extraction was checked against the header's total level; it was not visually verified inside the game.

The reader is adapted from the MIT project [melvor2sim](https://github.com/jtwilli/melvor2sim). See [provenance and modifications](vendor/melvor2sim/PROVENANCE.md).

## Migrating older outputs

Run `extract-character.ps1` to generate English v2 snapshots at the new default location before using cached queries. The v1 Portuguese contract is incompatible and is rejected rather than guessed. Old personal outputs remain ignored; the migration does not modify saves or translate player-created names.
